# 🚀 Azure AI Provisioner

<div align="center">

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Terraform](https://img.shields.io/badge/Terraform-7B42BC?style=for-the-badge&logo=terraform&logoColor=white)](https://www.terraform.io/)
[![Azure](https://img.shields.io/badge/Microsoft_Azure-0089D0?style=for-the-badge&logo=microsoft-azure&logoColor=white)](https://azure.microsoft.com/)
[![GitHub Codespaces](https://img.shields.io/badge/GitHub_Codespaces-181717?style=for-the-badge&logo=github&logoColor=white)](#-quick-start-with-github-codespaces)

**One-click Azure AI infrastructure deployment with real-time streaming logs** ✨

*Transform a simple form into a complete Azure AI environment in minutes*

</div>

---
## 1. What This Project Does
The application exposes a FastAPI web interface that:
1. Accepts a minimal form (base name + model choice + optional toggles) and deterministically generates compliant Azure resource names with a short suffix.
2. Writes a `terraform.tfvars` file reflecting those names, flags and defaults.
3. Executes `terraform init` (when needed) and `terraform apply -auto-approve` in a subprocess, streaming stdout/stderr over WebSocket to the browser in real time.
4. Reads `terraform output -json` and displays key resource information (non‑sensitive) in a result page.

Provisioned resource set (current):
- Resource Group
- Storage Account (created via `azapi_resource` — key-based auth disabled tenant policy workaround)
- Azure AI Services (foundation hosting for deployments & link with Foundry)
- Azure AI Foundry Hub + Project (with RBAC propagation wait)
- Azure OpenAI model deployment (`azurerm_cognitive_deployment` attached to AI Services)
- Key Vault (base for future secret integration)
- Log Analytics Workspace + Application Insights (workspace-based mode)
- (Optional) Azure AI Search

All resources follow a consistent naming pattern and rely on Azure AD / RBAC (no secret keys emitted) due to tenant policies forbidding shared key usage for Storage.

---
## 2. High-Level Architecture
```
Browser (Form + Live Log UI)
	|  (HTTP POST + WebSocket)
FastAPI Backend (app/main.py)
	| 1) Build names & tfvars
	| 2) Spawn terraform subprocess
	| 3) Stream lines via WebSocket
Terraform Root Module (terraform/)
	|-- azurerm + azapi providers
	|-- Creates Azure resource graph
Azure Platform Resources
```

Key design decisions:
- Single Python module keeps orchestration simple (intentional until complexity justifies refactor).
- `azapi_resource` chosen for Storage because azurerm provider data-plane polling fails under enforced “KeyBasedAuthenticationNotPermitted” policies.
- Workspace-based Application Insights adopted to avoid legacy ingestion/billing 404s.
- Explicit `time_sleep` resource used to absorb RBAC role assignment propagation before creating Foundry Project (MSI validation requirement).

---
## 3. Naming Convention
Pattern: `<base><code><rand>`
- `base`: user input sanitized (letters/digits)
- `code`: short mnemonic (rg, stg, ais, hub, prj, kv, appi, law, srch)
- `rand`: 5–6 lowercase alphanumeric chars
Storage capped < 24 chars, others respect Azure limits. Keep new resources aligned by extending the mapping in `app/main.py` (function generating names).

---
## 4. Dev Container & Codespaces
This repository is optimized for a containerized dev workflow (VS Code Dev Containers or GitHub Codespaces):

Benefits:
- Pre-installed: Python, Terraform, Azure CLI, environment tooling.
- Consistent reproducible environment (no “works on my machine”).
- Immediate `uvicorn` + Terraform readiness.

### 4.1 Open in GitHub Codespaces
If this repo lives on GitHub you can launch a Codespace (replace OWNER/REPO):
```markdown
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/OWNER/REPO?quickstart=1)
```

### 4.2 VS Code Dev Container (Local)
1. Install the “Dev Containers” extension.
2. Open the folder; if prompted, “Reopen in Container”.
3. The container should provision dependencies automatically (if a `.devcontainer` exists); else see Manual Setup below.

---
## 5. Manual (Non-Container) Prerequisites
Install locally if you do NOT use a dev container / Codespace:
- Python ≥ 3.10
- Terraform ≥ 1.6.0
- Azure CLI ≥ 2.60
- (Optional) Node.js if you plan to extend frontend assets

Login & subscription:
```bash
az login
az account set --subscription <SUBSCRIPTION_ID>
```

Create & activate virtual environment + deps:
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---
## 6. Running the Application
```bash
uvicorn app.main:app --reload
```
Browse: http://localhost:8000

Deployment UI steps:
1. Enter base name + choose model + optional flags.
2. Submit and watch streaming Terraform logs.
3. View summarized outputs after success.

---
## 7. Terraform Workflows
Directory: `terraform/`

Initialize (first time or after provider changes):
```bash
cd terraform
terraform init
```

Validate & plan:
```bash
terraform validate
terraform plan -lock=false
```

Apply (non-interactive, used by the app):
```bash
terraform apply -auto-approve
```

Destroy:
```bash
terraform destroy -auto-approve
```

Partial targeting (e.g. role assignment):
```bash
terraform apply -target=azurerm_role_assignment.hub_blob_contributor -auto-approve
```

---
## 8. Resource Inventory (Current)
| Component | Terraform Resource / Type | Notes |
|-----------|---------------------------|-------|
| Resource Group | `azurerm_resource_group` | Root scope |
| Storage Account | `azapi_resource` + `data.azurerm_storage_account` | Created via AzAPI (no key polling) |
| AI Services | `azurerm_ai_services` | Parent for model deployments |
| Foundry Hub | `azurerm_ai_foundry` | System-assigned identity |
| Foundry Project | `azurerm_ai_foundry_project` | Waits on RBAC sleep + identity |
| OpenAI Model Deployment | `azurerm_cognitive_deployment` | Uses AI Services (no separate cognitive account) |
| Key Vault | `azurerm_key_vault` | Base for future secrets (RBAC / access policy) |
| Log Analytics Workspace | `azurerm_log_analytics_workspace` | Metrics & logs aggregation |
| Application Insights | `azurerm_application_insights` | Workspace-based mode |
| Azure AI Search (optional) | `azurerm_search_service` | Controlled by `include_search` flag |

---
## 9. RBAC & Policy Considerations
Tenant policy blocks key-based Storage authentication. Mitigations:
- Storage deployed via AzAPI to skip provider’s key-based readiness polling.
- `allowSharedKeyAccess=false` & `defaultToOAuthAuthentication=true` set.
- Role assignments: Blob Data Contributor / Reader for Hub, AI Services, and current user.
- Sleep (`time_sleep.after_rbac`) ensures propagation before Foundry Project creation (avoids MSI validation 400).

Duplicate role or Key Vault access policy conflicts: remove or wrap in conditional instead of forcing import if rapid iteration is preferred.

---
## 10. Model Deployment Logic
The deployment resource (`azurerm_cognitive_deployment`) attaches the selected OpenAI model to the AI Services account:
- Default SKU: `GlobalStandard` (modifiable via variable).
- Model version left empty by design to consume latest available unless explicitly required.
- Safe model allowlist enforced in `app/main.py` (update both list and HTML dropdown to extend).

---
## 11. Live Log Streaming
The backend spawns Terraform as a subprocess, reading its stdout line-by-line and relaying over a WebSocket endpoint to the `deployment.html` template. Guidelines when extending:
- Keep reads non-blocking / incremental.
- If chaining extra CLI steps post-apply (e.g., CLI queries), stream them through the same channel for continuity.

---
## 12. Security Practices
- No account keys or connection strings exposed in outputs.
- Instrumentation key & App Insights connection string marked sensitive.
- Prefer retrieving ephemeral tokens via Azure CLI / Managed Identity for downstream usage.
- Future: replace access policies with full RBAC mode on Key Vault if tenant allows.

---
## 13. Extending the Project
Adding a new Azure resource:
1. Define variable in `variables.tf` (with sane default or required type).
2. Add naming code in `app/main.py` (extend the resource code map & tfvars writer).
3. Create Terraform block grouped under a header (match hash-line style).
4. Append outputs only if non-sensitive; otherwise rely on CLI retrieval.

Adding a new model option:
1. Add model name to `ALLOWED_MODEL_NAMES` in `app/main.py`.
2. Update `<select>` in `app/templates/index.html`.
3. (If different SKU required) introduce logic mapping model→SKU.

---
## 14. Troubleshooting (Common Issues)
| Symptom | Cause | Fix |
|---------|-------|-----|
| 403 KeyBasedAuthenticationNotPermitted (Storage) | azurerm provider polling with keys under restrictive policy | Use AzAPI resource (already implemented) |
| 400 ValidationError (Foundry Project MSI) | RBAC not propagated / missing identities | Ensure identities + wait (`time_sleep`) |
| 409 RoleAssignmentExists | Existing manual role assignment | Remove TF block or import resource; or widen scope to RG |
| Key Vault access policy already exists | Policy pre-created | Remove duplicated policy block or import |
| Model deployment fails (unsupported model) | Not in allowlist | Add to `ALLOWED_MODEL_NAMES` + UI select |

Increase `time_sleep` duration (e.g., 180s) if large tenants exhibit slower RBAC propagation.

---
## 15. Cleaning Up
```bash
cd terraform
terraform destroy -auto-approve
```

If state left partially applied, re-run `terraform destroy` after resolving any import/duplicate conflicts.

---
## 16. Contributing
Pull Requests welcome. Recommended steps:
1. Run `terraform validate` and a dry `plan` before submitting.
2. Keep new resource naming aligned with existing pattern.
3. Avoid exposing secrets in outputs or logs.

---
## 17. License
If a license is intended, add a `LICENSE` file (MIT / Apache-2.0 etc.). Currently unspecified.

---
## 18. Quick Reference Commands
```bash
# Start API locally
uvicorn app.main:app --reload

# Terraform core cycle
cd terraform
terraform init
terraform plan -lock=false
terraform apply -auto-approve
terraform destroy -auto-approve

# Inspect outputs JSON
terraform output -json | jq
```

---
## 19. Roadmap (Suggested Next Enhancements)
- Key Vault secret wiring (store endpoints / model metadata)
- Optional remote backend (Azure Storage state) once Storage provisioning stabilized
- Health endpoint & lightweight readiness probe
- Model SKU abstraction table for per‑model defaults
- Basic test harness (FastAPI testclient + mock Terraform)

---
Feel free to open issues for clarifications or propose improvements to onboarding, automation, or multi-tenant resilience.

