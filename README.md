# Azure AI Provisioner (FastAPI + Terraform)

This project provides a simple FastAPI web UI to provision Azure AI related resources using Terraform and Azure CLI:

Resources provisioned:
- Resource Group
- Storage Account
- Azure OpenAI (Cognitive Account kind=OpenAI)
- (Optional) Azure AI Search
- Azure AI Foundry Hub + Project (via Azure CLI)

Captured outputs include endpoints and resource names; some sensitive keys may require additional CLI retrieval steps.

## Prerequisites
- Python 3.10+
- Terraform >= 1.6.0 installed and in PATH
- Azure CLI (az) >= 2.60
- Logged in: `az login`
- Subscription set (if needed): `az account set --subscription <SUB_ID>`

## Install
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run application
```powershell
uvicorn app.main:app --reload
```
Navigate to: http://localhost:8000

## Deployment Flow
1. Fill the form (resource group base name, location, optional search, model deployment name).
2. Submit; logs stream in real time (Terraform then Azure CLI hub/project creation).
3. On success you are redirected to a results page listing collected outputs.

## Terraform State
Currently local state (kept inside `terraform/`). For multi-user scenarios consider remote state (Azure Storage backend).

## Keys Retrieval Notes
- OpenAI API keys: Use `az cognitiveservices account keys list -n <openai_account_name> -g <rg>` if needed.
- Search: Query keys can be obtained with `az search query-key list --service-name <search_name> -g <rg>`.
- Storage: Connection string via `az storage account show-connection-string -n <storage> -g <rg>`.
- Azure AI Foundry project API key (PAT) may require manual creation if not exposed directly.

## Improving Security
Do not persist raw keys in long-term storage. Consider integrating Azure Key Vault and referencing secrets.

## Future Enhancements
- Add Key Vault integration
- Add explicit retrieval of keys via CLI post-provision
- Add model deployment automation for Azure OpenAI (once supported/approved)
- Replace polling WebSocket loop with server push triggered on append

## Cleanup
```powershell
cd terraform
terraform destroy -auto-approve
```

