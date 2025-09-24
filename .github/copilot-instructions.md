# AI Assistant Instructions for this Repository

## Project Overview
FastAPI web app + Terraform implementing a "Multi-Environment Manager" (Terraform Cloud casero) for Azure AI resources. Creates AI Services, Foundry Hub & Project, model deployment, Storage, Log Analytics + App Insights, optional Azure AI Search. Features persistent deployment state, dashboard management, live log streaming, destroy functionality, and .env file generation for workshop/exercise integration.

**NEW: Completely refactored with modular service architecture** - Main application reduced from 856 to 221 lines through systematic service extraction and separation of concerns.

## Language restrictions
In the code, all messages, comments, log output, and variable names must be in English.
Also you have to describe the commit messages in English.

## Architecture Overview: Modular Multi-Environment Manager

### **New Modular Application Architecture**
- **`app/main.py`** (221 lines): FastAPI routes, lifespan events, basic configuration only
- **`app/config.py`**: Centralized application configuration and constants
- **`app/services/`**: Service layer with single-responsibility modules
- **`app/utils/`**: Utility functions for naming, file operations, .env generation
- **`terraform/`**: Modular IaC split into 6 files (main, ai-services, rbac, storage, search, monitoring)
- **`deployment_states/`**: Persistent storage for deployment state, logs, and metadata across container restarts
- **`app/templates/`**: Dashboard UI (`deployments.html`), live logs (`deployment.html`), results with .env download

### **Service Layer Architecture**
```
app/services/
├── validation_service.py    - Form validation & parameter checking
├── persistence_service.py   - State management & database operations  
├── azure_service.py         - Azure CLI authentication & credentials
├── terraform_service.py     - Infrastructure as Code operations
└── deployment_service.py    - High-level workflow orchestration
```

### **Utility Layer Architecture**
```
app/utils/
├── naming.py               - Azure-compliant resource name generation
├── file_operations.py      - Terraform file management & cleanup
└── env_generator.py        - IBM workshop format .env file generation
```

### **Deployment Lifecycle**
1. **Create**: Form validation → name generation → terraform orchestration → state persistence
2. **Manage**: Dashboard view of all deployments with status, actions, resource info
3. **Results**: View outputs, download IBM workshop-format .env file with all credentials
4. **Destroy**: Terraform destroy orchestration → state cleanup

## Key Directories / Files

### **Application Layer (Modular)**
- `app/main.py`: FastAPI routes, WebSocket endpoints, startup configuration (221 lines)
- `app/config.py`: Application settings, constants, directory configuration
- `app/services/validation_service.py`: Form validation and parameter checking
- `app/services/persistence_service.py`: Deployment state management and database operations
- `app/services/azure_service.py`: Azure authentication and credential retrieval
- `app/services/terraform_service.py`: Infrastructure operations and retry logic
- `app/services/deployment_service.py`: High-level workflow orchestration
- `app/utils/naming.py`: Azure-compliant resource naming with collision avoidance
- `app/utils/file_operations.py`: Terraform file management for isolated deployments
- `app/utils/env_generator.py`: IBM workshop format .env file generation
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

### **Deployment Management (Service-Orchestrated)**
```bash
# Create new deployment (modular)
POST /deploy → validation_service.validate_deployment_form() → deployment_service.run_full_deployment()
  ├── azure_service.ensure_azure_authentication()
  ├── terraform_service.terraform_init() + terraform_apply()
  ├── azure_service.get_ai_services_keys() + get_storage_credentials()
  └── persistence_service.save_deployment_state()

# Destroy deployment (modular)
POST /destroy/{id} → deployment_service.run_full_destroy()
  ├── terraform_service.terraform_destroy()
  └── persistence_service.save_deployment_state() + cleanup

# View dashboard
GET /deployments → persistence_service.get_all_deployments()

# Download .env (IBM workshop format)
GET /download-env/{id} → env_generator.generate_ibm_env_content()
```

### **State Persistence (Centralized Service)**
- **Startup**: `persistence_service.load_all_deployments()` restores DEPLOYMENTS dict from storage
- **Runtime**: `persistence_service.save_deployment_state()` called on status changes
- **Logging**: `persistence_service.append_log()` handles all deployment logging
- **Structure**: Each deployment gets own directory with terraform state, tfvars, metadata.json

### **Live Log Streaming (Service Integration)**
- WebSocket endpoint `/ws/{deployment_id}` streams terraform stdout via callbacks
- `terraform_service` functions accept `log_callback` parameter for real-time streaming
- Both create and destroy operations use same streaming mechanism with service coordination
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

### **Deployment State Management (Service Pattern)**
```python
# Service-based state management
from app.services.persistence_service import save_deployment_state, load_all_deployments

# Always save state on status changes
DEPLOYMENTS[deployment_id]["status"] = "terraform|completed|destroying|destroyed|error"
persistence_service.save_deployment_state(deployment_id, DEPLOYMENTS[deployment_id])

# Modern lifespan events (replaces @app.on_event)
@asynccontextmanager
async def lifespan(app: FastAPI):
    DEPLOYMENTS.update(persistence_service.load_all_deployments())
    yield  # Application runs
    print("Application shutting down")
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

## Modular Architecture Patterns

### **Service Layer Design**
```python
# Each service has single responsibility and clear interface
# validation_service.py - Form validation only
def validate_deployment_form(params) -> Tuple[bool, Optional[str], Optional[Dict]]

# persistence_service.py - State management only  
def save_deployment_state(deployment_id: str, data: Dict) -> None

# azure_service.py - Azure operations only
def ensure_azure_authentication(subscription_id: Optional[str]) -> Tuple[bool, str, Optional[str]]

# terraform_service.py - Infrastructure operations only
async def terraform_apply(deployment_dir: Path, log_callback: Optional[callable]) -> None

# deployment_service.py - High-level orchestration
async def run_full_deployment(deployment_id: str, deployments: Dict, dirs: Paths) -> None
```

### **Service Integration Patterns**
- **Dependency injection**: Pass required parameters explicitly (no global state)
- **Callback integration**: Use log_callback functions for real-time streaming
- **Error boundaries**: Each service handles its own error types
- **Configuration centralized**: All constants in app/config.py

### **Import Organization**
```python
# app/main.py structure
from .config import APP_TITLE, STATIC_DIR, TERRAFORM_DIR  # Configuration
from .utils.naming import build_names                      # Utilities  
from .services.validation_service import validate_form    # Services
from .services.deployment_service import run_deployment   # Orchestration
```

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

## Modular Development Guidelines

### **When Adding New Features**
1. **Identify the service layer** - Which service should handle this functionality?
2. **Follow single responsibility** - Each service should have one clear purpose
3. **Use dependency injection** - Pass required data as parameters, avoid global state
4. **Add to appropriate config** - New constants go in app/config.py
5. **Update imports** - Maintain clean import structure in main.py

### **Service Layer Guidelines**  
- **validation_service.py**: Add new form validation logic here
- **persistence_service.py**: Add new database/state operations here
- **azure_service.py**: Add new Azure CLI or credential operations here  
- **terraform_service.py**: Add new infrastructure operations here
- **deployment_service.py**: Add new high-level workflows here
- **utils/**: Add reusable utility functions (naming, file ops, etc.)

### **Testing Individual Services**
```python
# Test validation service
from app.services.validation_service import validate_deployment_form
result = validate_deployment_form("test", "eastus", "gpt-4o", "sp-name", "2025-12-01")

# Test terraform service  
from app.services.terraform_service import generate_tfvars_content
content = generate_tfvars_content(params, names)

# Test azure service
from app.services.azure_service import ensure_azure_authentication  
success, message, subscription = ensure_azure_authentication(None)
```
