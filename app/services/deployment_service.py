"""
Deployment orchestration service for Azure AI Multi-Environment Manager.

This service coordinates high-level deployment workflows by orchestrating
between persistence, Azure, and Terraform services.
"""
import json
import subprocess
from pathlib import Path
from typing import Dict, Any

from .persistence_service import save_deployment_state, append_log
from .azure_service import (
    ensure_azure_authentication, 
    get_ai_services_keys, 
    get_storage_credentials, 
    get_search_service_key
)
from .terraform_service import (
    terraform_init, 
    terraform_apply, 
    terraform_destroy,
    generate_tfvars_content, 
    parse_terraform_outputs, 
    write_tfvars_file
)
from ..utils.file_operations import copy_terraform_files, cleanup_terraform_files


async def ensure_azure_login(deployment_id: str, deployments: Dict[str, Dict], deployment_params: Dict[str, Any]):
    """Ensure Azure CLI logged in and subscription selected automatically."""
    explicit = deployment_params.get("subscription_id") or None
    success, message, chosen = ensure_azure_authentication(explicit)
    
    append_log(deployment_id, f"[AUTH] {message}")
    
    if not success:
        raise RuntimeError(f"Azure authentication failed: {message}")
    
    # Persist auto-selected subscription so terraform.tfvars includes it
    if chosen and not explicit and deployments.get(deployment_id):
        try:
            deployments[deployment_id].setdefault("params", {})["subscription_id"] = chosen
        except Exception:
            pass


async def run_full_deployment(
    deployment_id: str, 
    deployments: Dict[str, Dict], 
    deployment_states_dir: Path,
    terraform_dir: Path
):
    """Execute complete deployment workflow with all Azure resources.
    
    Args:
        deployment_id: Unique deployment identifier
        deployments: Global deployments dictionary (for state updates)
        deployment_states_dir: Base directory for deployment persistence
        terraform_dir: Directory containing terraform configuration files
    """
    data = deployments[deployment_id]
    names = data["names"]
    params = data["params"]
    
    try:
        deployments[deployment_id]["status"] = "terraform"
        # Save initial deployment state persistently
        save_deployment_state(deployment_id, deployments[deployment_id])
        
        # Ensure Azure login first (before terraform so provider auth works)
        await ensure_azure_login(deployment_id, deployments, params)
        
        # Create isolated deployment directory with terraform files
        deployment_dir = deployment_states_dir / deployment_id
        deployment_dir.mkdir(exist_ok=True)
        
        # Copy terraform files to deployment directory for isolated execution
        append_log(deployment_id, "[SETUP] Creating isolated terraform workspace")
        copy_terraform_files(terraform_dir, deployment_dir)
        append_log(deployment_id, f"[SETUP] Copied terraform files to {deployment_dir}")
        
        # Prepare terraform.tfvars in deployment directory
        tfvars_content = generate_tfvars_content(params, names)
        write_tfvars_file(deployment_dir, tfvars_content)
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

        # Terraform init & apply - now executed in isolated deployment directory
        append_log(deployment_id, f"[TERRAFORM] Executing in isolated workspace: {deployment_dir}")
        
        # Create log callback function to bridge with our append_log system
        def log_callback(line: str):
            append_log(deployment_id, line)
            
        await terraform_init(deployment_dir, log_callback=log_callback)
        await terraform_apply(deployment_dir, log_callback=log_callback, max_retries=2)
        
        # Terraform outputs - parse from deployment directory
        outputs = parse_terraform_outputs(deployment_dir)
        deployments[deployment_id]["outputs"].update(outputs)
        
        # Log foundry endpoint availability
        if outputs.get("foundry_project_endpoint"):
            append_log(deployment_id, f"[INFO] Foundry project endpoint: {outputs['foundry_project_endpoint']}")
        else:
            append_log(deployment_id, "[INFO] Foundry project endpoint not exposed by provider yet or null.")

        # Foundry project handled by Terraform
        deployments[deployment_id]["status"] = "foundry"

        # Actual resource group name (prefixed in tfvars)
        rg_name = f"RG-{params['resource_group_base']}"

        # Retrieve Azure OpenAI (AI Services) keys & endpoint alias
        append_log(deployment_id, "Retrieving Azure OpenAI (AI Services) keys...")
        ai_keys = get_ai_services_keys(names["ai_services_name"], rg_name)
        if ai_keys:
            deployments[deployment_id]["outputs"].update({
                "azure_openai_endpoint": outputs.get("openai_endpoint") or outputs.get("ai_services_endpoint"),
                "azure_openai_api_key_primary": ai_keys.get("key1"),
                "azure_openai_api_key_secondary": ai_keys.get("key2"),
            })
            # Provide friendly alias for deployment name if present
            if outputs.get("openai_deployment_name"):
                deployments[deployment_id]["outputs"].setdefault(
                    "openai_model_deployment_name", outputs["openai_deployment_name"]
                )
        else:
            append_log(deployment_id, "[WARN] Could not fetch Azure OpenAI keys")

        # Retrieve Storage connection string & key
        append_log(deployment_id, "Retrieving Storage connection string...")
        storage_creds = get_storage_credentials(names["storage_account_name"], rg_name)
        if storage_creds:
            deployments[deployment_id]["outputs"].update({
                "storage_connection_string": storage_creds.get("connection_string"),
                "storage_account_key": storage_creds.get("account_key")
            })
        else:
            append_log(deployment_id, "[WARN] Could not fetch Storage credentials")

        # Retrieve Search query key (if search included)
        if params['include_search']:
            append_log(deployment_id, "Retrieving Search service query key...")
            search_creds = get_search_service_key(names["search_service_name"], rg_name)
            if search_creds:
                deployments[deployment_id]["outputs"].update({
                    "azure_ai_search_url": search_creds.get("search_url"),
                    "azure_ai_search_key": search_creds.get("search_key"),
                })
            else:
                append_log(deployment_id, "[WARN] Could not fetch Search credentials")

        # Clean up terraform files but keep state and variables for potential destroy
        cleanup_terraform_files(deployment_dir)
        append_log(deployment_id, "[CLEANUP] Removed terraform files, kept state and variables")
        
        deployments[deployment_id]["status"] = "completed"
        append_log(deployment_id, "Deployment completed successfully")
        # Save deployment state persistently (include outputs so dashboard flags it)
        save_deployment_state(deployment_id, deployments[deployment_id], deployments[deployment_id].get("outputs", {}))
        
    except Exception as e:  # noqa
        # Clean up terraform files on error too
        deployment_dir = deployment_states_dir / deployment_id
        if deployment_dir.exists():
            cleanup_terraform_files(deployment_dir)
            append_log(deployment_id, "[CLEANUP] Removed terraform files due to error")
        
        deployments[deployment_id]["status"] = "error"
        append_log(deployment_id, f"ERROR: {e}")
        # Save deployment state even on error (outputs may be partial)
        save_deployment_state(deployment_id, deployments[deployment_id], deployments[deployment_id].get("outputs", {}))


async def run_full_destroy(
    deployment_id: str, 
    deployments: Dict[str, Dict], 
    deployment_states_dir: Path,
    terraform_dir: Path
):
    """Execute complete deployment destroy workflow.
    
    Args:
        deployment_id: Unique deployment identifier
        deployments: Global deployments dictionary (for state updates)
        deployment_states_dir: Base directory for deployment persistence
        terraform_dir: Directory containing terraform configuration files
    """
    try:
        deployments[deployment_id]["status"] = "destroying"
        # Save initial destroy state persistently
        save_deployment_state(deployment_id, deployments[deployment_id])
        
        # Ensure Azure login first
        await ensure_azure_login(deployment_id, deployments, deployments[deployment_id]["params"])
        
        # Setup isolated deployment directory for destroy
        deployment_dir = deployment_states_dir / deployment_id
        
        # Verify state files exist
        state_file = deployment_dir / "terraform.tfstate"
        
        if not state_file.exists():
            append_log(deployment_id, f"[ERROR] No terraform state found for deployment {deployment_id[:8]}")
            raise RuntimeError(f"Cannot destroy deployment {deployment_id[:8]}: no terraform state found")
            
        # Copy current terraform files to deployment directory for destroy
        append_log(deployment_id, "[SETUP] Creating isolated terraform workspace for destroy")
        copy_terraform_files(terraform_dir, deployment_dir)
        append_log(deployment_id, f"[SETUP] Using terraform files with existing state in {deployment_dir}")
        
        # Run terraform destroy with retry logic - executed in isolated deployment directory  
        append_log(deployment_id, f"[TERRAFORM] Destroying from isolated workspace: {deployment_dir}")
        append_log(deployment_id, "Starting terraform destroy...")
        
        # Create log callback function to bridge with our append_log system
        def log_callback(line: str):
            append_log(deployment_id, line)
            
        await terraform_destroy(deployment_dir, log_callback=log_callback, max_retries=2)
        
        # If we reach here, destroy succeeded
        deployments[deployment_id]["status"] = "destroyed"
        append_log(deployment_id, "Resources destroyed successfully")
        
        # Clean up terraform files in deployment directory after successful destroy
        cleanup_terraform_files(deployment_dir)
        append_log(deployment_id, "[CLEANUP] Cleaned up terraform files after successful destroy")
        
        # Remove outputs since resources no longer exist
        deployments[deployment_id]["outputs"] = {}
        
        # Save final deployment state persistently
        save_deployment_state(deployment_id, deployments[deployment_id])
        
    except Exception as e:  # noqa
        deployments[deployment_id]["status"] = "destroy_error"
        append_log(deployment_id, f"ERROR during destroy: {e}")
        # Save deployment state even on error
        save_deployment_state(deployment_id, deployments[deployment_id])