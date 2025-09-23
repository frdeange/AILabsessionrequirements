import asyncio
import json
import os
import random
import string
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from dotenv import load_dotenv

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
TERRAFORM_DIR = BASE_DIR / "terraform"
DEPLOYMENT_STATES_DIR = BASE_DIR / "deployment_states"
DEPLOYMENTS_DB_FILE = DEPLOYMENT_STATES_DIR / "deployments.json"

app = FastAPI(title="Azure AI Provisioner")

app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))

# In-memory store for deployments (legacy - will be replaced by persistent storage)
DEPLOYMENTS: Dict[str, Dict] = {}

@app.on_event("startup")
async def startup_event():
    """Load persisted deployments on startup"""
    global DEPLOYMENTS
    persisted_deployments = load_all_deployments()
    DEPLOYMENTS.update(persisted_deployments)
    print(f"Loaded {len(persisted_deployments)} persisted deployments")

###############################################
# Deployment Persistence Functions
###############################################

def load_deployments_db() -> Dict:
    """Load deployments database from persistent storage"""
    try:
        if DEPLOYMENTS_DB_FILE.exists():
            with open(DEPLOYMENTS_DB_FILE, 'r') as f:
                return json.load(f)
        else:
            # Create initial structure
            initial_db = {
                "deployments": {},
                "metadata": {
                    "version": "1.0", 
                    "created": "2025-09-23T09:50:00Z",
                    "description": "Multi-Environment Manager - Deployment Database"
                }
            }
            save_deployments_db(initial_db)
            return initial_db
    except Exception as e:
        print(f"Error loading deployments database: {e}")
        return {"deployments": {}, "metadata": {}}

def save_deployments_db(db: Dict) -> None:
    """Save deployments database to persistent storage"""
    try:
        DEPLOYMENT_STATES_DIR.mkdir(exist_ok=True)
        with open(DEPLOYMENTS_DB_FILE, 'w') as f:
            json.dump(db, f, indent=2)
    except Exception as e:
        print(f"Error saving deployments database: {e}")

def save_deployment_state(deployment_id: str, deployment_data: Dict, outputs: Dict = None) -> None:
    """Save deployment state and metadata persistently"""
    try:
        # Create deployment directory
        deployment_dir = DEPLOYMENT_STATES_DIR / deployment_id
        deployment_dir.mkdir(exist_ok=True)
        
        # Save terraform state if exists
        terraform_state = TERRAFORM_DIR / "terraform.tfstate"
        if terraform_state.exists():
            import shutil
            shutil.copy(terraform_state, deployment_dir / "terraform.tfstate")
        
        # Save terraform tfvars if exists
        terraform_tfvars = TERRAFORM_DIR / "terraform.tfvars"
        if terraform_tfvars.exists():
            import shutil
            shutil.copy(terraform_tfvars, deployment_dir / "terraform.tfvars")
        
        # Save deployment metadata
        metadata = {
            "deployment_id": deployment_id,
            "deployment_data": deployment_data,
            "outputs": outputs or {},
            "saved_at": "2025-09-23T09:50:00Z",
            "has_state": terraform_state.exists(),
            "status": deployment_data.get("status", "unknown")
        }
        
        with open(deployment_dir / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Update main database
        db = load_deployments_db()
        db["deployments"][deployment_id] = {
            "id": deployment_id,
            "name": deployment_data.get("params", {}).get("resource_group_base", "Unknown"),
            "status": deployment_data.get("status", "unknown"),
            "created_at": "2025-09-23T09:50:00Z",
            "has_state": terraform_state.exists(),
            "outputs_available": bool(outputs),
            "region": deployment_data.get("params", {}).get("location", "unknown"),
            "include_search": deployment_data.get("params", {}).get("include_search", False),
            "resource_names": deployment_data.get("names", {})
        }
        save_deployments_db(db)
        
    except Exception as e:
        print(f"Error saving deployment state for {deployment_id}: {e}")

def load_deployment_state(deployment_id: str) -> Dict:
    """Load deployment state from persistent storage"""
    try:
        deployment_dir = DEPLOYMENT_STATES_DIR / deployment_id
        if not deployment_dir.exists():
            return {}
        
        metadata_file = deployment_dir / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading deployment state for {deployment_id}: {e}")
        return {}

def get_all_deployments() -> Dict:
    """Get list of all deployments from database"""
    db = load_deployments_db()
    return db.get("deployments", {})

def load_all_deployments() -> Dict[str, Dict]:
    """Load all deployments with full state from persistent storage"""
    deployments = {}
    try:
        db = load_deployments_db()
        for deployment_id in db.get("deployments", {}):
            metadata = load_deployment_state(deployment_id)
            if metadata and "deployment_data" in metadata:
                deployments[deployment_id] = metadata["deployment_data"]
        return deployments
    except Exception as e:
        print(f"Error loading all deployments: {e}")
        return {}

# Simple naming utility respecting some Azure limits
# Storage account: 3-24 lower case letters/numbers only
# Search service: 2-60 lower case letters/numbers
# Hub / Project (use similar pattern, enforce <= 40 for safety)

def random_suffix(length: int = 5) -> str:
    """Generate a random lowercase suffix of given length."""
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))


def sanitize_base(base: str) -> str:
    allowed = string.ascii_lowercase + string.digits
    base = base.lower()
    return ''.join(c for c in base if c in allowed)


def build_names(base: str) -> Dict[str, str]:
    """Build resource names with suffix ensuring Azure naming constraints.

    Strategy: truncate base to leave room for 3-char code + suffix.
    """
    base_s = sanitize_base(base)
    suf = random_suffix()
    def compose(limit: int, code: str) -> str:
        room_for_base = limit - len(code) - len(suf)
        truncated = base_s[: max(0, room_for_base)]
        return (truncated + code + suf)[:limit]
    storage = compose(24, "stg")
    search = compose(60, "src")
    kv = compose(24, "kv")
    ais = compose(40, "ais")
    hub = compose(40, "hub")
    appi = compose(40, "appi")
    project = compose(30, "prj")
    law = compose(40, "law")
    return {
        "storage_account_name": storage,
        "search_service_name": search,
        "ai_services_name": ais,
        "ai_foundry_hub_name": hub,
        "app_insights_name": appi,
        "log_analytics_workspace_name": law,
        "project_name": project,
        "suffix": suf,
    }


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


ALLOWED_MODEL_NAMES = {"gpt-4.1","gpt-4.1-mini","gpt-4o","gpt-4o-mini"}

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
    base_clean = sanitize_base(resource_group_base)
    if len(base_clean) < 3:
        return templates.TemplateResponse("index.html", {"request": request, "error": "Resource group base too short."})
    if len(base_clean) > 15:
        return templates.TemplateResponse("index.html", {"request": request, "error": "Resource group base too long (max 15)."})

    names = build_names(base_clean)
    if openai_model_name not in ALLOWED_MODEL_NAMES:
        return templates.TemplateResponse("index.html", {"request": request, "error": "Invalid model selection."})

    # Defaults simplificados para el deployment (no se piden al usuario):
    openai_model_version = ""  # omit to let platform choose
    # Deployment name igual al nombre de modelo (petición usuario)
    model_deployment_name = openai_model_name
    openai_deployment_sku = "GlobalStandard"
    enable_model_deployment = True
    deployment_id = str(uuid.uuid4())
    include_search_flag = str(include_search).lower() in {"on", "1", "true", "yes"}

    DEPLOYMENTS[deployment_id] = {
        "status": "starting",
        "logs": [],
        "outputs": {},
        "names": names,
        "params": {
            "resource_group_base": base_clean,
            "location": location,
            "include_search": include_search_flag,
            "enable_model_deployment": enable_model_deployment,
            "openai_model_name": openai_model_name,
            "openai_model_version": openai_model_version,
            "openai_deployment_sku": openai_deployment_sku,
            "model_deployment_name": model_deployment_name,
            # fallback to environment AZ_SUBSCRIPTION_ID if form empty
            "subscription_id": ((subscription_id or "").strip() or os.getenv("AZ_SUBSCRIPTION_ID", "").strip()),
            "service_principal_name": service_principal_name.strip(),
            "secret_expiration_date": secret_expiration_date.strip(),
        },
    }
    asyncio.create_task(run_full_deployment(deployment_id))
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
    asyncio.create_task(run_full_destroy(deployment_id))
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
    
    # Generate .env content matching IBM Masterclass format
    env_content = "# =============================================================================\n"
    env_content += "# IBM Masterclass Day 1 - Environment Configuration\n"
    env_content += "# =============================================================================\n"
    env_content += f"# Generated from Azure AI deployment: {deployment_id[:8]}\n"
    env_content += f"# Created at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
    env_content += "# Never commit .env files with real credentials to version control!\n\n"
    
    # Azure Subscription & Service Principal
    env_content += "# =============================================================================\n"
    env_content += "# Azure Subscription & Service Principal\n"
    env_content += "# =============================================================================\n"
    if outputs.get("subscription_id"):
        env_content += f'AZURE_SUBSCRIPTION_ID="{outputs["subscription_id"]}"\n'
    elif data.get("params", {}).get("subscription_id"):
        env_content += f'AZURE_SUBSCRIPTION_ID="{data["params"]["subscription_id"]}"\n'
    if outputs.get("tenant_id"):
        env_content += f'AZURE_TENANT_ID="{outputs["tenant_id"]}"\n'
    if outputs.get("service_principal_app_id"):
        env_content += f'AZURE_CLIENT_ID="{outputs["service_principal_app_id"]}"\n'
    if outputs.get("service_principal_secret"):
        env_content += f'AZURE_CLIENT_SECRET="{outputs["service_principal_secret"]}"\n'
    
    # Azure OpenAI Configuration
    env_content += "\n# =============================================================================\n"
    env_content += "# Azure OpenAI Configuration (EX1, EX3, EX4, EX5, EX6)\n"
    env_content += "# =============================================================================\n"
    if outputs.get("openai_endpoint"):
        env_content += f'AZURE_OPENAI_ENDPOINT="{outputs["openai_endpoint"]}"\n'
    if outputs.get("azure_openai_key"):
        env_content += f'AZURE_OPENAI_API_KEY="{outputs["azure_openai_key"]}"\n'
    if outputs.get("openai_deployment_name"):
        env_content += f'AZURE_OPENAI_DEPLOYMENT_NAME="{outputs["openai_deployment_name"]}"\n'
    # Fixed values from the workshop
    env_content += 'AZURE_OPENAI_API_VERSION="2024-12-01-preview"\n'
    env_content += 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT="text-embedding-3-small"\n'
    
    # Azure AI Foundry / AI Studio
    env_content += "\n# =============================================================================\n"
    env_content += "# Azure AI Foundry / AI Studio (EX2, EX4, EX5, EX6)\n"
    env_content += "# =============================================================================\n"
    # Use AI inference endpoint for Foundry (different from project URL)
    if outputs.get("ai_inference_endpoint"):
        env_content += f'AI_FOUNDRY_ENDPOINT="{outputs["ai_inference_endpoint"]}"\n'
    elif outputs.get("azure_foundry_project_url"):
        # Fallback to project URL if inference endpoint not available
        env_content += f'AI_FOUNDRY_ENDPOINT="{outputs["azure_foundry_project_url"]}"\n'
    # Same key as OpenAI
    if outputs.get("azure_openai_key"):
        env_content += f'AI_FOUNDRY_API_KEY="{outputs["azure_openai_key"]}"\n'
    # Same deployment name as OpenAI
    if outputs.get("openai_deployment_name"):
        env_content += f'AI_FOUNDRY_DEPLOYMENT_NAME="{outputs["openai_deployment_name"]}"\n'
    
    # Azure AI Search Configuration
    env_content += "\n# =============================================================================\n"
    env_content += "# Azure AI Search Configuration (EX3)\n"
    env_content += "# =============================================================================\n"
    if outputs.get("search_service_endpoint"):
        env_content += f'AZURE_SEARCH_ENDPOINT="{outputs["search_service_endpoint"]}"\n'
    if outputs.get("azure_search_admin_key"):
        env_content += f'AZURE_SEARCH_API_KEY="{outputs["azure_search_admin_key"]}"\n'
    # Fixed index name from workshop
    env_content += 'AZURE_SEARCH_INDEX_NAME="masterclass-index"\n'
    
    # Logging and Monitoring
    env_content += "\n# =============================================================================\n"
    env_content += "# Logging and Monitoring (Optional)\n"
    env_content += "# =============================================================================\n"
    env_content += 'LOG_LEVEL="INFO"\n'
    if outputs.get("app_insights_connection_string"):
        env_content += f'APPLICATION_INSIGHTS_CONNECTION_STRING="{outputs["app_insights_connection_string"]}"\n'
    
    # Return as downloadable file
    return Response(
        content=env_content,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename=azure-ai-{deployment_id[:8]}.env"}
    )


@app.websocket("/ws/{deployment_id}")
async def ws_logs(websocket: WebSocket, deployment_id: str):
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
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return


def append_log(deployment_id: str, line: str):
    DEPLOYMENTS[deployment_id]["logs"].append(line)


async def run_cmd_stream(deployment_id: str, cmd: list, cwd: Path | None = None, env: Dict[str, str] | None = None, max_retries: int = 0, retry_delay: int = 30):
    append_log(deployment_id, f"[CMD] {' '.join(cmd)}")
    
    for attempt in range(max_retries + 1):
        if attempt > 0:
            append_log(deployment_id, f"[RETRY] Attempt {attempt + 1}/{max_retries + 1} after {retry_delay}s delay")
            await asyncio.sleep(retry_delay)
            
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd) if cwd else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env or os.environ.copy(),
        )
        assert process.stdout
        
        output_lines = []
        async for line in process.stdout:  # type: ignore
            line_text = line.decode(errors='ignore').rstrip()
            append_log(deployment_id, line_text)
            output_lines.append(line_text)
            
        rc = await process.wait()
        append_log(deployment_id, f"[EXIT {rc}] {' '.join(cmd)}")
        
        if rc == 0:
            return  # Success
            
        # Check if it's a retryable error (409 Conflict)
        output_text = '\n'.join(output_lines)
        is_retryable = (
            attempt < max_retries and 
            "terraform apply" in ' '.join(cmd) and
            ("409" in output_text or "Conflict" in output_text or "provisioning state is not terminal" in output_text)
        )
        
        if is_retryable:
            append_log(deployment_id, f"[RETRY] Detected retryable error (409 Conflict). Will retry in {retry_delay}s...")
            continue
        else:
            # Not retryable or max retries exceeded
            raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    
    raise RuntimeError(f"Command failed after {max_retries + 1} attempts: {' '.join(cmd)}")


def azure_logged_in() -> bool:
    """Return True if 'az account show' succeeds (user logged in)."""
    try:
        subprocess.check_output(["az", "account", "show"], stderr=subprocess.STDOUT)
        return True
    except Exception:  # noqa
        return False


def attempt_az_login(device_code: bool = False) -> bool:
    """Attempt interactive Azure CLI login. device_code toggles --use-device-code."""
    cmd = ["az", "login"] + (["--use-device-code"] if device_code else [])
    try:
        subprocess.check_call(cmd)
        return True
    except Exception:
        return False


def list_subscriptions() -> list[dict]:
    try:
        raw = subprocess.check_output(["az", "account", "list", "--all", "-o", "json"]).decode()
        return json.loads(raw)
    except Exception:
        return []


def auto_pick_subscription(explicit: str | None) -> tuple[str | None, str]:
    """Return (subscription_id, strategy_msg)."""
    if explicit:
        return explicit, f"explicit({explicit})"
    env_sub = os.getenv("AZ_SUBSCRIPTION_ID")
    if env_sub:
        return env_sub, f"env({env_sub})"
    subs = list_subscriptions()
    if not subs:
        return None, "none-found"
    if len(subs) == 1:
        return subs[0].get("id"), "single"
    # Try default flag
    default_candidates = [s for s in subs if s.get("isDefault")]
    if default_candidates:
        return default_candidates[0].get("id"), "default-flag"
    # Fallback first
    return subs[0].get("id"), "first"


def set_subscription(sub_id: str) -> bool:
    try:
        subprocess.check_call(["az", "account", "set", "--subscription", sub_id])
        return True
    except Exception:
        return False


async def ensure_azure_login(deployment_id: str):
    """Ensure Azure CLI logged in and subscription selected automatically.

    Order of precedence:
      1. Explicit form field
      2. AZ_SUBSCRIPTION_ID env var
      3. If only one subscription -> use it
      4. Subscription marked isDefault
      5. First in list
    """
    if os.getenv("AZ_SKIP_LOGIN_CHECK", "").lower() in {"1", "true", "yes"}:
        append_log(deployment_id, "[AUTH] Skipping Azure login check (AZ_SKIP_LOGIN_CHECK set).")
        return
    logged_in = azure_logged_in()
    if not logged_in:
        append_log(deployment_id, "[AUTH] No Azure CLI session. Attempting 'az login'...")
        if not attempt_az_login(False):
            append_log(deployment_id, "[AUTH] Standard login failed. Trying device code flow...")
            if not attempt_az_login(True):
                raise RuntimeError("Azure CLI login failed (both standard and device code). Please login manually inside the container.")
        append_log(deployment_id, "[AUTH] Login successful.")
    else:
        append_log(deployment_id, "[AUTH] Azure CLI session detected.")

    explicit = DEPLOYMENTS.get(deployment_id, {}).get("params", {}).get("subscription_id") or None
    chosen, strategy = auto_pick_subscription(explicit)
    if not chosen:
        append_log(deployment_id, "[AUTH] Could not determine subscription automatically (none available).")
        return
    if set_subscription(chosen):
        append_log(deployment_id, f"[AUTH] Subscription set ({strategy}): {chosen}")
        # Persist auto-selected subscription so terraform.tfvars includes it
        try:
            if DEPLOYMENTS.get(deployment_id):
                if not explicit:
                    DEPLOYMENTS[deployment_id].setdefault("params", {})["subscription_id"] = chosen
        except Exception:  # noqa
            pass
    else:
        append_log(deployment_id, f"[WARN] Failed to set subscription ({chosen}).")


async def run_full_deployment(deployment_id: str):
    data = DEPLOYMENTS[deployment_id]
    names = data["names"]
    params = data["params"]
    try:
        DEPLOYMENTS[deployment_id]["status"] = "terraform"
        # Save initial deployment state persistently
        save_deployment_state(deployment_id, DEPLOYMENTS[deployment_id])
        # Ensure Azure login first (before terraform so provider auth works)
        await ensure_azure_login(deployment_id)
        # Prepare terraform.tfvars
        tfvars_content = (
            f"rg_name = \"RG-{params['resource_group_base']}\"\n"
            f"location = \"{params['location']}\"\n"
            f"include_search = {str(params['include_search']).lower()}\n"  # value from form; ensure checkbox sets 'on'
            f"storage_account_name = \"{names['storage_account_name']}\"\n"
            f"search_service_name = \"{names['search_service_name']}\"\n"
            f"foundry_project_name = \"{names['project_name']}\"\n"
            f"ai_services_name = \"{names['ai_services_name']}\"\n"
            f"ai_foundry_hub_name = \"{names['ai_foundry_hub_name']}\"\n"
            f"app_insights_name = \"{names['app_insights_name']}\"\n"
            f"log_analytics_workspace_name = \"{names['log_analytics_workspace_name']}\"\n"
            f"enable_model_deployment = {str(params['enable_model_deployment']).lower()}\n"
            f"model_deployment_name = \"{params['model_deployment_name']}\"\n"
            f"openai_model_name = \"{params['openai_model_name']}\"\n"
            f"openai_model_version = \"{params['openai_model_version']}\"\n"
            f"openai_deployment_sku = \"{params['openai_deployment_sku']}\"\n"
            f"service_principal_name = \"{params['service_principal_name']}\"\n"
            f"secret_expiration_date = \"{params['secret_expiration_date']}\""
        )
        if params.get("subscription_id"):
            tfvars_content += f"\nsubscription_id = \"{params['subscription_id']}\""
        tfvars_path = TERRAFORM_DIR / "terraform.tfvars"
        tfvars_path.write_text(tfvars_content, encoding="utf-8")
        append_log(deployment_id, f"[DEBUG] include_search={params['include_search']} search_service_name={names['search_service_name']}")

        # Basic quota / usage precheck placeholder (future enhancement could call ARM usage APIs)
        append_log(deployment_id, "[PRECHECK] Environment validation placeholder (quotas not yet checked).")
        try:
            acct = subprocess.check_output(["az", "account", "show", "-o", "json"]).decode()
            sub_info = json.loads(acct)
            append_log(deployment_id, f"[PRECHECK] Active subscription: {sub_info.get('id')} - {sub_info.get('name')}")
        except Exception as e:  # noqa
            append_log(deployment_id, f"[PRECHECK][WARN] Could not read 'az account show': {e}")
        append_log(deployment_id, "[PRECHECK] (Future) Query specific quotas for Cognitive, AI Foundry and Storage.")

        # Terraform init & apply
        await run_cmd_stream(deployment_id, ["terraform", "init"], cwd=TERRAFORM_DIR)
        await run_cmd_stream(deployment_id, ["terraform", "apply", "-auto-approve"], cwd=TERRAFORM_DIR, max_retries=2, retry_delay=60)
        # Terraform outputs
        out_raw = subprocess.check_output(["terraform", "output", "-json"], cwd=str(TERRAFORM_DIR))
        outputs = json.loads(out_raw.decode())
        simplified = {k: v.get("value") for k, v in outputs.items()}
        DEPLOYMENTS[deployment_id]["outputs"].update(simplified)

        # Standardize endpoint aliases (ensure three distinct endpoints if derivable)
        ai_services_ep = simplified.get("ai_services_endpoint") or simplified.get("ai_services_endpoint")
        openai_ep = simplified.get("openai_endpoint")
        inference_ep = simplified.get("ai_inference_endpoint")
        # Fallback derivations if terraform outputs missing (based on cognitive endpoint)
        if ai_services_ep and not openai_ep and ".cognitiveservices.azure.com" in ai_services_ep:
            openai_ep = ai_services_ep.replace(".cognitiveservices.azure.com", ".openai.azure.com")
        if ai_services_ep and not inference_ep and ".cognitiveservices.azure.com" in ai_services_ep:
            inference_ep = ai_services_ep.replace(".cognitiveservices.azure.com", ".services.ai.azure.com")
        DEPLOYMENTS[deployment_id]["outputs"].setdefault("azure_ai_services_endpoint", ai_services_ep)
        DEPLOYMENTS[deployment_id]["outputs"].setdefault("azure_openai_endpoint", openai_ep)
        DEPLOYMENTS[deployment_id]["outputs"].setdefault("azure_ai_inference_endpoint", inference_ep)

        # Alias for foundry endpoint if present (user-friendly key)
        if simplified.get("foundry_project_endpoint"):
            DEPLOYMENTS[deployment_id]["outputs"].setdefault(
                "azure_ai_foundry_project_endpoint", simplified["foundry_project_endpoint"],
            )
        else:
            append_log(deployment_id, "[INFO] Foundry project endpoint not exposed by provider yet or null.")

        # Foundry project handled by Terraform
        DEPLOYMENTS[deployment_id]["status"] = "foundry"

        # Actual resource group name (prefixed in tfvars)
        rg_name = f"RG-{params['resource_group_base']}"

        # Retrieve Azure OpenAI (AI Services) keys & endpoint alias
        try:
            append_log(deployment_id, "Retrieving Azure OpenAI (AI Services) keys...")
            ai_keys_raw = subprocess.check_output([
                "az", "cognitiveservices", "account", "keys", "list",
                "-n", names["ai_services_name"],
                "-g", rg_name,
                "-o", "json"
            ])
            ai_keys_json = json.loads(ai_keys_raw.decode())
            if isinstance(ai_keys_json, dict):
                DEPLOYMENTS[deployment_id]["outputs"].update({
                    "azure_openai_endpoint": simplified.get("openai_endpoint") or simplified.get("ai_services_endpoint"),
                    "azure_openai_api_key_primary": ai_keys_json.get("key1"),
                    "azure_openai_api_key_secondary": ai_keys_json.get("key2"),
                })
            # Provide friendly alias for deployment name if present
            if simplified.get("openai_deployment_name"):
                DEPLOYMENTS[deployment_id]["outputs"].setdefault(
                    "openai_model_deployment_name", simplified["openai_deployment_name"]
                )
        except Exception as e:  # noqa
            append_log(deployment_id, f"[WARN] Could not fetch Azure OpenAI keys: {e}")

        # Retrieve Storage connection string & key
        try:
            append_log(deployment_id, "Retrieving Storage connection string...")
            conn_raw = subprocess.check_output([
                "az", "storage", "account", "show-connection-string",
                "-n", names["storage_account_name"],
                "-g", rg_name,
                "-o", "json"
            ])
            conn_json = json.loads(conn_raw.decode())
            DEPLOYMENTS[deployment_id]["outputs"].update({
                "storage_connection_string": conn_json.get("connectionString")
            })
            keys_raw = subprocess.check_output([
                "az", "storage", "account", "keys", "list",
                "-n", names["storage_account_name"],
                "-g", rg_name,
                "-o", "json"
            ])
            keys_json = json.loads(keys_raw.decode())
            if isinstance(keys_json, list) and keys_json:
                DEPLOYMENTS[deployment_id]["outputs"].update({
                    "storage_account_key": keys_json[0].get("value")
                })
        except Exception as e:  # noqa
            append_log(deployment_id, f"[WARN] Could not fetch Storage keys: {e}")

        # Retrieve Search query key (if search included)
        if params['include_search']:
            try:
                append_log(deployment_id, "Retrieving Search service query key...")
                search_keys_raw = subprocess.check_output([
                    "az", "search", "query-key", "list",
                    "--service-name", names["search_service_name"],
                    "-g", rg_name,
                    "-o", "json"
                ])
                search_keys_json = json.loads(search_keys_raw.decode())
                first_key = None
                if isinstance(search_keys_json, list) and search_keys_json:
                    first_key = search_keys_json[0].get("key")
                DEPLOYMENTS[deployment_id]["outputs"].update({
                    "azure_ai_search_url": f"https://{names['search_service_name']}.search.windows.net" if first_key else None,
                    "azure_ai_search_key": first_key,
                })
            except Exception as e:  # noqa
                append_log(deployment_id, f"[WARN] Could not fetch Search keys: {e}")

        DEPLOYMENTS[deployment_id]["status"] = "completed"
        append_log(deployment_id, "Deployment completed successfully")
        # Save deployment state persistently
        save_deployment_state(deployment_id, DEPLOYMENTS[deployment_id])
    except Exception as e:  # noqa
        DEPLOYMENTS[deployment_id]["status"] = "error"
        append_log(deployment_id, f"ERROR: {e}")
        # Save deployment state even on error
        save_deployment_state(deployment_id, DEPLOYMENTS[deployment_id])


async def run_full_destroy(deployment_id: str):
    """Execute terraform destroy for a deployment"""
    data = DEPLOYMENTS[deployment_id]
    try:
        DEPLOYMENTS[deployment_id]["status"] = "destroying"
        # Save initial destroy state persistently
        save_deployment_state(deployment_id, DEPLOYMENTS[deployment_id])
        
        # Ensure Azure login first
        await ensure_azure_login(deployment_id)
        
        # Copy state file back to terraform directory
        deployment_dir = DEPLOYMENT_STATES_DIR / deployment_id
        state_file = deployment_dir / "terraform.tfstate"
        tfvars_file = deployment_dir / "terraform.tfvars"
        
        # Copy terraform state and tfvars back to terraform directory
        if state_file.exists():
            import shutil
            shutil.copy(state_file, TERRAFORM_DIR / "terraform.tfstate")
            append_log(deployment_id, "Copied terraform state for destroy operation")
        
        if tfvars_file.exists():
            import shutil
            shutil.copy(tfvars_file, TERRAFORM_DIR / "terraform.tfvars")
            append_log(deployment_id, "Copied terraform tfvars for destroy operation")
        
        # Run terraform destroy
        append_log(deployment_id, "Starting terraform destroy...")
        destroy_process = await asyncio.create_subprocess_exec(
            "terraform", "destroy", "-auto-approve",
            cwd=TERRAFORM_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=dict(os.environ, **{"TF_LOG": "INFO"})
        )
        
        # Stream destroy output
        while True:
            line = await destroy_process.stdout.readline()
            if not line:
                break
            line_str = line.decode("utf-8", errors="ignore").strip()
            if line_str:
                append_log(deployment_id, line_str)
        
        await destroy_process.wait()
        
        if destroy_process.returncode == 0:
            DEPLOYMENTS[deployment_id]["status"] = "destroyed"
            append_log(deployment_id, "Resources destroyed successfully")
            
            # Clean up state files after successful destroy
            terraform_state = TERRAFORM_DIR / "terraform.tfstate"
            if terraform_state.exists():
                terraform_state.unlink()
                append_log(deployment_id, "Cleaned up terraform state file")
            
            # Remove outputs since resources no longer exist
            DEPLOYMENTS[deployment_id]["outputs"] = {}
            
        else:
            DEPLOYMENTS[deployment_id]["status"] = "destroy_error"
            append_log(deployment_id, f"Terraform destroy failed with exit code {destroy_process.returncode}")
        
        # Save final deployment state persistently
        save_deployment_state(deployment_id, DEPLOYMENTS[deployment_id])
        
    except Exception as e:  # noqa
        DEPLOYMENTS[deployment_id]["status"] = "destroy_error"
        append_log(deployment_id, f"ERROR during destroy: {e}")
        # Save deployment state even on error
        save_deployment_state(deployment_id, DEPLOYMENTS[deployment_id])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
