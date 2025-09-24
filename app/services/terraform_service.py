"""
Terraform service for Azure AI Multi-Environment Manager.

This service handles all Terraform operations including command execution,
retry logic for Azure conflicts, and tfvars generation.
"""
import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any


async def run_terraform_command(
    cmd: List[str], 
    cwd: Optional[Path] = None, 
    env: Optional[Dict[str, str]] = None, 
    max_retries: int = 0, 
    retry_delay: int = 30,
    log_callback: Optional[callable] = None
) -> None:
    """Execute terraform command with streaming output and retry logic.
    
    Args:
        cmd: Command and arguments to execute
        cwd: Working directory for command execution
        env: Environment variables (defaults to current environment)
        max_retries: Maximum number of retry attempts for 409 conflicts
        retry_delay: Delay in seconds between retry attempts
        log_callback: Function to call for each log line (deployment_id, line)
    
    Raises:
        RuntimeError: If command fails after all retry attempts
    """
    if log_callback:
        log_callback(f"[CMD] {' '.join(cmd)}")
    
    for attempt in range(max_retries + 1):
        if attempt > 0:
            if log_callback:
                log_callback(f"[RETRY] Attempt {attempt + 1}/{max_retries + 1} after {retry_delay}s delay")
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
            if log_callback:
                log_callback(line_text)
            output_lines.append(line_text)
            
        rc = await process.wait()
        if log_callback:
            log_callback(f"[EXIT {rc}] {' '.join(cmd)}")
        
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
            if log_callback:
                log_callback(f"[RETRY] Detected retryable error (409 Conflict). Will retry in {retry_delay}s...")
            continue
        else:
            # Not retryable or max retries exceeded
            raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    
    raise RuntimeError(f"Command failed after {max_retries + 1} attempts: {' '.join(cmd)}")


def generate_tfvars_content(params: Dict[str, Any], names: Dict[str, str]) -> str:
    """Generate terraform.tfvars content from deployment parameters.
    
    Args:
        params: Deployment parameters dictionary
        names: Generated resource names dictionary
        
    Returns:
        Complete tfvars file content as string
    """
    tfvars_content = (
        f"rg_name = \"RG-{params['resource_group_base']}\"\n"
        f"location = \"{params['location']}\"\n"
        f"include_search = {str(params['include_search']).lower()}\n"
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
        
    return tfvars_content


def parse_terraform_outputs(deployment_dir: Path) -> Dict[str, Any]:
    """Parse terraform outputs from deployment directory.
    
    Args:
        deployment_dir: Directory containing terraform state and outputs
        
    Returns:
        Parsed terraform outputs as simplified dictionary
    """
    try:
        # Try to get outputs from terraform state
        out_raw = subprocess.check_output(["terraform", "output", "-json"], cwd=str(deployment_dir))
        outputs = json.loads(out_raw.decode())
        simplified = {k: v.get("value") for k, v in outputs.items()}
        
        # Standardize endpoint aliases (ensure three distinct endpoints if derivable)
        ai_services_ep = simplified.get("ai_services_endpoint") or simplified.get("ai_services_endpoint")
        openai_ep = simplified.get("openai_endpoint")
        inference_ep = simplified.get("ai_inference_endpoint")
        
        # Fallback derivations if terraform outputs missing (based on cognitive endpoint)
        if ai_services_ep and not openai_ep and ".cognitiveservices.azure.com" in ai_services_ep:
            openai_ep = ai_services_ep.replace(".cognitiveservices.azure.com", ".openai.azure.com")
        if ai_services_ep and not inference_ep and ".cognitiveservices.azure.com" in ai_services_ep:
            inference_ep = ai_services_ep.replace(".cognitiveservices.azure.com", ".services.ai.azure.com")
            
        simplified.setdefault("azure_ai_services_endpoint", ai_services_ep)
        simplified.setdefault("azure_openai_endpoint", openai_ep)
        simplified.setdefault("azure_ai_inference_endpoint", inference_ep)
        
        # Alias for foundry endpoint if present (user-friendly key)
        if simplified.get("foundry_project_endpoint"):
            simplified.setdefault("azure_ai_foundry_project_endpoint", simplified["foundry_project_endpoint"])
            
        return simplified
    except Exception as e:
        print(f"Error parsing terraform outputs: {e}")
        return {}


def write_tfvars_file(deployment_dir: Path, content: str) -> None:
    """Write terraform.tfvars file to deployment directory.
    
    Args:
        deployment_dir: Directory to write tfvars file
        content: Content of tfvars file
    """
    deployment_dir.mkdir(exist_ok=True)
    tfvars_path = deployment_dir / "terraform.tfvars"
    tfvars_path.write_text(content, encoding="utf-8")


async def terraform_init(deployment_dir: Path, log_callback: Optional[callable] = None) -> None:
    """Initialize terraform in deployment directory.
    
    Args:
        deployment_dir: Directory containing terraform files
        log_callback: Function to call for each log line
    """
    await run_terraform_command(["terraform", "init"], cwd=deployment_dir, log_callback=log_callback)


async def terraform_apply(deployment_dir: Path, log_callback: Optional[callable] = None, max_retries: int = 2) -> None:
    """Apply terraform configuration in deployment directory.
    
    Args:
        deployment_dir: Directory containing terraform files
        log_callback: Function to call for each log line
        max_retries: Maximum retry attempts for 409 conflicts
    """
    await run_terraform_command(
        ["terraform", "apply", "-auto-approve"], 
        cwd=deployment_dir, 
        log_callback=log_callback,
        max_retries=max_retries,
        retry_delay=60
    )


async def terraform_destroy(deployment_dir: Path, log_callback: Optional[callable] = None, max_retries: int = 2) -> None:
    """Destroy terraform resources in deployment directory.
    
    Args:
        deployment_dir: Directory containing terraform files
        log_callback: Function to call for each log line
        max_retries: Maximum retry attempts for conflicts
    """
    await run_terraform_command(
        ["terraform", "destroy", "-auto-approve"], 
        cwd=deployment_dir, 
        log_callback=log_callback,
        max_retries=max_retries,
        retry_delay=30
    )