# Deployment States Directory

This directory contains the persistent state for the Multi-Environment Manager.

## Structure:
```
deployment_states/
├── deployments.json          # Database of all deployments
├── {deployment_id}/
│   ├── terraform.tfstate     # Terraform state file
│   ├── terraform.tfvars      # Variables used for deployment
│   ├── deployment.log        # Deployment logs
│   └── metadata.json         # Deployment metadata
└── README.md                # This file
```

## Purpose:
- **Persistence**: State survives container restarts
- **Multi-environment**: Multiple concurrent deployments
- **Management**: View, update, destroy individual deployments
- **History**: Track all deployment activities

## Files:
- `deployments.json` - Central database of all deployments
- Individual deployment folders contain their specific state and logs

This enables the "Terraform Cloud casero" functionality for managing multiple Azure AI environments.