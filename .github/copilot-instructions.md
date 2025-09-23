# AI Assistant Instructions for this Repository

## Project Overview
FastAPI web app + Terraform implementing a "Multi-Environment Manager" (Terraform Cloud casero) for Azure AI resources. Creates AI Services, Foundry Hub & Project, model deployment, Storage, Log Analytics + App Insights, optional Azure AI Search. Features persistent deployment state, dashboard management, live log streaming, destroy functionality, and .env file generation for workshop/exercise integration.

## Language restrictions
In the code, all messages, comments, log output, and variable names must be in English.
Also you have to describe the commit messages in English.

## Architecture Overview: Multi-Environment Manager

### **Core Components**
- **`app/main.py`**: FastAPI app with deployment persistence, WebSocket streaming, destroy capability, .env generation
- **`terraform/`**: Modular IaC split into 6 files (main, ai-services, rbac, storage, search, monitoring)
- **`deployment_states/`**: Persistent storage for deployment state, logs, and metadata across container restarts
- **`app/templates/`**: Dashboard UI (`deployments.html`), live logs (`deployment.html`), results with .env download

### **Deployment Lifecycle**
1. **Create**: Form → tfvars generation → terraform apply with live streaming → state persistence
2. **Manage**: Dashboard view of all deployments with status, actions, resource info
3. **Results**: View outputs, download IBM workshop-format .env file with all credentials
4. **Destroy**: Terraform destroy with live streaming → state cleanup

## Key Directories / Files

### **Application Layer**
- `app/main.py`: Central FastAPI app (800+ lines) - deployment management, persistence, WebSocket streaming
- `app/templates/deployments.html`: Multi-environment dashboard with destroy/view actions
- `app/templates/results.html`: Outputs display + .env download button (IBM workshop format)
- `app/templates/deployment.html`: Live log streaming for create/destroy operations

### **Infrastructure Layer** 
- `terraform/main.tf`: Core resources (RG, data sources, service principal)
- `terraform/ai-services.tf`: Hub, Project, model deployment logic
- `terraform/rbac.tf`: 15+ role assignments for Hub MSI, current user, service principal
- `terraform/storage.tf`: azapi_resource for AAD-only storage (tenant policy compliance)
- `terraform/search.tf`: Optional AI Search with conditional deployment
- `terraform/monitoring.tf`: Log Analytics + App Insights workspace-based setup

### **Persistence Layer**
- `deployment_states/deployments.json`: Central database of all deployments
- `deployment_states/{deployment_id}/`: Per-deployment state, tfvars, logs, metadata

## Critical Workflows

### **Deployment Management**
```bash
# Create new deployment
POST /deploy → run_full_deployment() → save_deployment_state()

# Destroy deployment  
POST /destroy/{id} → run_full_destroy() → state cleanup

# View dashboard
GET /deployments → load all persistent deployments

# Download .env (IBM workshop format)
GET /download-env/{id} → formatted environment variables
```

### **State Persistence**
- **Startup**: `load_all_deployments()` restores DEPLOYMENTS dict from persistent storage
- **Runtime**: `save_deployment_state()` called on status changes (terraform, completed, destroyed)
- **Structure**: Each deployment gets own directory with terraform state, tfvars, metadata.json

### **Live Log Streaming**
- WebSocket endpoint `/ws/{deployment_id}` streams terraform stdout line-by-line
- Both create and destroy operations use same streaming mechanism
- Frontend auto-redirects on completion messages

## Terraform Architecture (Modular)

### **Resource Dependencies**
```
main.tf (RG, data sources) 
  ├── ai-services.tf (Hub → Project with MSI dependency)
  ├── storage.tf (azapi_resource for AAD-only)
  ├── search.tf (conditional on include_search)
  ├── monitoring.tf (Log Analytics → App Insights)
  └── rbac.tf (15+ role assignments, time_sleep for propagation)
```

### **Critical Patterns**
- **Conditional resources**: `count = var.include_search ? 1 : 0` for optional Search
- **azapi_resource**: Used for Storage (tenant policy), Hub, Project (provider limitations)
- **RBAC propagation**: `time_sleep` resource before Project creation for MSI role readiness
- **Naming strategy**: `build_names()` in app/main.py - deterministic short names + random suffix

## Project-Specific Conventions

### **Deployment State Management**
```python
# Always save state on status changes
DEPLOYMENTS[deployment_id]["status"] = "terraform|completed|destroying|destroyed|error"
save_deployment_state(deployment_id, DEPLOYMENTS[deployment_id])

# Load at startup
@app.on_event("startup")
async def startup_event():
    DEPLOYMENTS.update(load_all_deployments())
```

### **.env Generation (IBM Workshop Format)**
- Matches exact IBM Masterclass format with sections and comments
- Fixed values: `AZURE_OPENAI_API_VERSION="2024-12-01-preview"`, `AZURE_SEARCH_INDEX_NAME="masterclass-index"`
- Duplicated keys: `AI_FOUNDRY_*` uses same values as `AZURE_OPENAI_*` for workshop compatibility

### **UI State Management**
- Dashboard shows deployment count, status chips with color coding
- Actions conditional on state: View (completed), Delete (has_state), Update (disabled)
- JavaScript handles destroy confirmation, .env download with progress indication

## Common Pitfalls & Workarounds

### **Terraform State Issues**
- **Storage 403**: Must use `azapi_resource` + AAD RBAC (tenant policy forbids key-based auth)
- **Project MSI validation**: Requires `time_sleep` after RBAC assignments before Project creation
- **Role assignment conflicts**: Remove/skip rather than import during rapid iterations

### **Deployment Persistence**
- **State file handling**: Copy terraform.tfstate to/from deployment_states/ directory for destroy operations
- **Subscription detection**: Fallback chain: explicit form → env vars → `az account show` → subscription list
- **WebSocket connection**: Non-blocking subprocess pipe reading, proper error handling

### **Multi-Environment Conflicts**
- Use deployment-specific directories to avoid terraform state conflicts
- Always copy state files back to terraform/ directory before operations
- Clean up terraform.tfstate after successful destroy

## Integration Points

### **Azure CLI Integration**
- `ensure_azure_login()`: Subscription detection and login verification before terraform
- Respect subscription resolution order: explicit > env vars > current > single > first listed

### **Workshop/Exercise Integration**
- `/download-env/{id}` generates IBM workshop-compatible .env files
- Includes all credentials, fixed API versions, deployment names for seamless exercise integration

## Security Patterns
- **No key-based storage auth**: azapi_resource + AAD RBAC only
- **Sensitive outputs**: Mark keys as sensitive in terraform outputs
- **Service Principal**: Auto-generated with expiration date, proper secret rotation

## Testing / Validation
```bash
# Validate all terraform files
cd terraform && terraform validate

# Test deployment persistence
# Check deployment_states/ structure after operations

# Verify .env download
# curl /download-env/{id} → should match IBM workshop format
```

## Quick Commands
- **Start app**: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- **Validate terraform**: `cd terraform && terraform validate`
- **Manual destroy**: `cd terraform && terraform destroy -auto-approve`
- **Check persistence**: `ls deployment_states/` and `cat deployment_states/deployments.json`
