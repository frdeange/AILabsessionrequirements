# AI Assistant Instructions for this Repository

## Project Overview
FastAPI web app + Terraform to provision Azure AI resources (AI Services, Foundry Hub & Project, model deployment, Key Vault, Storage, Log Analytics + App Insights, optional Azure AI Search). UI triggers infra provisioning; backend generates `terraform.tfvars` and streams `terraform apply` logs to the browser. Some resources now created via `azapi_resource` fallback (Storage) due to tenant policy forbidding key-based auth.

## Language restrictions
In the code, all messages, comments, log output, and variable names must be in English.
Also you have to describe the commit messages in English.

## Key Directories / Files
- `app/main.py`: FastAPI app, form handling, Azure CLI subscription detection, name building, tfvars generation, WebSocket log streaming.
- `app/templates/*.html`: Jinja2 templates (`index.html` form, `results.html` outputs, `deployment.html` live logs, `base.html`).
- `app/static/css/style.css`: UI styling (dark/light support hints, layout tweaks).
- `terraform/`: IaC module (main definitions), includes `main.tf`, `variables.tf`, `outputs.tf`, `providers.tf`.
- `.github/copilot-instructions.md`: (this file) guidance for AI agents.

## Provisioning Flow
1. User submits minimal form (model selection + base name, other values derived).
2. Backend builds deterministic short names + random suffix (e.g. `<base>rgxxxx`, `<base>stgxxxx`).
3. Writes `terraform/terraform.tfvars` with generated names & toggles.
4. Runs `terraform init` (if needed) and `terraform apply -auto-approve` while streaming stdout over WebSocket.
5. On completion, reads `terraform output -json` to display resource info.

## Resource Architecture (Why)
- Application Insights now workspace-based (`Log Analytics Workspace` + linkage) to avoid classic ingestion/billing feature 404s.
- Storage created via `azapi_resource` to bypass provider data-plane polling that fails under tenant policy (Shared Key disabled).
- RBAC enforced: `shared_access_key_enabled=false` and role assignments (Blob Data Contributor / Reader) for hub, AI Services, current user.
- AI Foundry Hub + Project layered: Project depends on RBAC propagation (sleep) due to MSI requirement error if roles not ready.
- Model deployment uses `azurerm_cognitive_deployment` attached to AI Services (no standalone OpenAI account resource).

## Important Terraform Patterns
- Conditional counts: optional search service & model deployment.
- Role assignments may conflict if pre-existing: strategy is to remove/skip rather than import during rapid iterations.
- Added `time_sleep` to mitigate eventual consistency for RBAC before creating Foundry Project.
- Storage outputs switched to data source due to azapi creation (use `data.azurerm_storage_account.stg`).

## Naming Strategy
Implemented in `app/main.py` (function building names): base slug + short resource code + random 5–6 char suffix. Keep names within Azure limits (<= 24 for storage). If adding new resources replicate this pattern for consistency.

## Azure Auth & Subscription Resolution
Backend tries: explicit subscription form value (if added later) > env vars > `az account show` current > single subscription fallback > first listed. Avoid hardcoding subscription in Terraform; pass via variable if override needed.

## Adding New Resources
1. Add variables in `variables.tf` and ensure they are written in tfvars writer.
2. Follow existing naming pattern (extend name map & codes).
3. Prefer referencing existing RG & location variables.
4. For RBAC-sensitive resources, add role assignments early (Resource Group scope if possible) + consider sleep for propagation if MSI dependent.

## Common Pitfalls & Workarounds
- Storage create 403 (KeyBasedAuthenticationNotPermitted): solved using `azapi_resource` + AAD RBAC; do not reintroduce `azurerm_storage_account` unless tenant policy changes.
- AI Foundry Project 400 MSI validation: ensure identity blocks and RBAC wait (`time_sleep`).
- Duplicate Key Vault access policies / role assignments: remove conflicting resource or import; avoid silent recreation loops.
- Avoid using model version unless explicitly required (left empty for latest).

## Live Log Streaming
WebSocket endpoint captures Terraform process output line-by-line. If modifying, ensure non-blocking reading (currently subprocess pipe). For new long-running tasks, append to same stream to keep UX consistent.

## Outputs Handling
`terraform/outputs.tf` deliberately excludes sensitive values except when necessary (Instrumentation Key marked sensitive). Prefer retrieving secret keys via CLI or Key Vault rather than outputs.

## Extending Model Options
Safe list: ALLOWED_MODEL_NAMES in `app/main.py`. To add: update the list, adjust UI dropdown (index.html), no other Terraform change required unless SKU/model constraints differ.

## Testing / Validation Tips
- Run `terraform validate` inside `terraform/` after edits.
- Use `terraform plan -lock=false` to preview without blocking active state operations.
- For iterative RBAC tweaks, target apply with `-target=azurerm_role_assignment.name` if partial.

## Security Considerations
- No account keys surfaced (policy enforces this). Use Azure AD + RBAC.
- Do not add secrets to outputs; prefer Key Vault integration if secrets become necessary.

## When Adding Automation
If you must script Azure CLI steps post-provision (e.g., retrieving keys), integrate after successful apply and stream those logs similarly; ensure CLI calls respect subscription resolution logic.

## Style / Conventions Recap
- Python: keep logic centralized in `app/main.py` (single-file simplicity). If complexity grows, split by concerns (naming, terraform_runner, azure_auth) but preserve current naming patterns.
- Terraform: keep all in root module for now; group sections with clear header comments (follow existing delimiter style of hash lines + title).

## Quick Commands (reference)
- Start app: `uvicorn app.main:app --reload`
- Destroy infra: `cd terraform && terraform destroy -auto-approve`

Provide feedback if any area needs deeper detail (e.g., adding tests, refactoring app into packages, or handling secrets via Key Vault).
