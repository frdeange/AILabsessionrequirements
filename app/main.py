import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from typing import Dict, Optional, AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Import configuration
from .config import (
    APP_TITLE, STATIC_DIR, TEMPLATES_DIR,
    TERRAFORM_DIR, DEPLOYMENT_STATES_DIR,
    DEFAULT_MODEL_VERSION, DEFAULT_DEPLOYMENT_SKU, DEFAULT_MODEL_DEPLOYMENT_ENABLED,
    WEBSOCKET_UPDATE_INTERVAL
)

# Import utilities
from .utils.naming import build_names
from .utils.env_generator import generate_env_content, generate_env_filename

# Import services  
from .services.persistence_service import (
    load_all_deployments, get_all_deployments, save_deployment_state
)
from .services.deployment_service import run_full_deployment, run_full_destroy
from .services.validation_service import validate_deployment_form, render_form_error

# Global deployments store (in-memory cache of persistent state)
DEPLOYMENTS: Dict[str, Dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application startup and shutdown events"""
    # Startup: Load persisted deployments
    global DEPLOYMENTS
    persisted_deployments = load_all_deployments()
    DEPLOYMENTS.update(persisted_deployments)
    print(f"Loaded {len(persisted_deployments)} persisted deployments")
    
    yield  # Application runs here
    
    # Shutdown: Could add cleanup logic here if needed
    print("Application shutting down")


# FastAPI application setup with lifespan
app = FastAPI(title=APP_TITLE, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/deployments", response_class=HTMLResponse)
async def deployments_dashboard(request: Request):
    """Dashboard showing all deployments with management options"""
    try:
        deployments = get_all_deployments()
        return templates.TemplateResponse("deployments.html", {
            "request": request, 
            "deployments": deployments
        })
    except Exception as e:
        return templates.TemplateResponse("deployments.html", {
            "request": request, 
            "deployments": {},
            "error": f"Error loading deployments: {e}"
        })


@app.post("/deploy")
async def start_deploy(
    request: Request,
    resource_group_base: str = Form(...),
    location: str = Form(...),
    include_search: Optional[str] = Form(None),
    openai_model_name: str = Form("gpt-4.1"),
    subscription_id: Optional[str] = Form(None),
    service_principal_name: str = Form(...),
    secret_expiration_date: str = Form(...),
):
    # Validate form inputs
    is_valid, error_message, validated_params = validate_deployment_form(
        resource_group_base, location, openai_model_name, 
        service_principal_name, secret_expiration_date,
        include_search, subscription_id
    )
    
    if not is_valid:
        return render_form_error(templates, request, error_message)
    
    # Generate resource names and deployment ID
    names = build_names(validated_params["resource_group_base_clean"])
    deployment_id = str(uuid.uuid4())
    
    # Create deployment record with configuration defaults
    DEPLOYMENTS[deployment_id] = {
        "status": "starting",
        "logs": [],
        "outputs": {},
        "names": names,
        "params": {
            "resource_group_base": validated_params["resource_group_base_clean"],
            "location": validated_params["location"],
            "include_search": validated_params["include_search"],
            "enable_model_deployment": DEFAULT_MODEL_DEPLOYMENT_ENABLED,
            "openai_model_name": validated_params["openai_model_name"],
            "openai_model_version": DEFAULT_MODEL_VERSION,
            "openai_deployment_sku": DEFAULT_DEPLOYMENT_SKU,
            "model_deployment_name": validated_params["openai_model_name"],  # Use model name as deployment name
            "subscription_id": validated_params["subscription_id"] or os.getenv("AZ_SUBSCRIPTION_ID", "").strip(),
            "service_principal_name": validated_params["service_principal_name"],
            "secret_expiration_date": validated_params["secret_expiration_date"],
        },
    }
    asyncio.create_task(run_full_deployment(deployment_id, DEPLOYMENTS, DEPLOYMENT_STATES_DIR, TERRAFORM_DIR))
    return RedirectResponse(url=f"/deployment/{deployment_id}", status_code=302)


@app.post("/destroy/{deployment_id}")
async def start_destroy(deployment_id: str, request: Request):
    """Start the destroy process for a deployment"""
    data = DEPLOYMENTS.get(deployment_id)
    if not data:
        return JSONResponse({"error": "Deployment not found"}, status_code=404)
    
    # Check if deployment has terraform state
    deployment_dir = DEPLOYMENT_STATES_DIR / deployment_id
    state_file = deployment_dir / "terraform.tfstate"
    if not state_file.exists():
        return JSONResponse({"error": "No terraform state found for this deployment"}, status_code=400)
    
    # Update status to destroying
    DEPLOYMENTS[deployment_id]["status"] = "destroying"
    DEPLOYMENTS[deployment_id]["logs"] = []  # Clear old logs
    save_deployment_state(deployment_id, DEPLOYMENTS[deployment_id])
    
    # Start destroy task
    asyncio.create_task(run_full_destroy(deployment_id, DEPLOYMENTS, DEPLOYMENT_STATES_DIR, TERRAFORM_DIR))
    return JSONResponse({"success": True, "redirect": f"/deployment/{deployment_id}"})


@app.get("/deployment/{deployment_id}", response_class=HTMLResponse)
async def deployment_status(deployment_id: str, request: Request):
    data = DEPLOYMENTS.get(deployment_id)
    if not data:
        return HTMLResponse("Deployment not found", status_code=404)
    return templates.TemplateResponse("deployment.html", {"request": request, "deployment_id": deployment_id, "data": data})


@app.get("/results/{deployment_id}", response_class=HTMLResponse)
async def deployment_results(deployment_id: str, request: Request):
    data = DEPLOYMENTS.get(deployment_id)
    if not data:
        return HTMLResponse("Deployment not found", status_code=404)
    if data.get("status") != "completed":
        return RedirectResponse(url=f"/deployment/{deployment_id}")
    return templates.TemplateResponse("results.html", {"request": request, "deployment_id": deployment_id, "data": data})


@app.get("/download-env/{deployment_id}")
async def download_env_file(deployment_id: str):
    """Generate and download a .env file with all deployment outputs"""
    data = DEPLOYMENTS.get(deployment_id)
    if not data:
        return JSONResponse({"error": "Deployment not found"}, status_code=404)
    
    outputs = data.get("outputs", {})
    if not outputs:
        return JSONResponse({"error": "No outputs available for this deployment"}, status_code=400)
    
    # Generate .env content using utility function
    env_content = generate_env_content(
        deployment_id=deployment_id,
        outputs=outputs, 
        params=data.get("params", {})
    )
    
    # Return as downloadable file
    filename = generate_env_filename(deployment_id)
    return Response(
        content=env_content,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )





@app.websocket("/ws/{deployment_id}")
async def ws_logs(websocket: WebSocket, deployment_id: str):
    """WebSocket endpoint for streaming deployment logs in real-time"""
    await websocket.accept()
    if deployment_id not in DEPLOYMENTS:
        await websocket.send_text("Invalid deployment id")
        await websocket.close()
        return
        
    last_index = 0
    try:
        while True:
            logs = DEPLOYMENTS[deployment_id]["logs"]
            if last_index < len(logs):
                for entry in logs[last_index:]:
                    await websocket.send_text(entry)
                last_index = len(logs)
            await asyncio.sleep(WEBSOCKET_UPDATE_INTERVAL)
    except WebSocketDisconnect:
        return


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
