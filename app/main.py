import asyncio
import json
import os
import random
import string
import subprocess
import uuid
from pathlib import Path
from typing import Dict, Optional
from dotenv import load_dotenv

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
TERRAFORM_DIR = BASE_DIR / "terraform"

app = FastAPI(title="Azure AI Provisioner")

app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))

# In-memory store for deployments
DEPLOYMENTS: Dict[str, Dict] = {}

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
    except Exception as e:  # noqa
        DEPLOYMENTS[deployment_id]["status"] = "error"
        append_log(deployment_id, f"ERROR: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
