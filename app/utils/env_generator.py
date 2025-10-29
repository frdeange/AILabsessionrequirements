"""
Environment file generator for Azure AI deployments.

This module generates .env files containing all necessary Azure AI service 
credentials and configurations for easy integration with AI projects.
"""
from datetime import datetime
from typing import Dict, Optional


def generate_env_content(deployment_id: str, outputs: Dict, params: Optional[Dict] = None) -> str:
    """Generate .env file content with Azure AI credentials.
    
    Args:
        deployment_id: Unique deployment identifier
        outputs: Terraform outputs containing service credentials
        params: Deployment parameters (optional)
        
    Returns:
        Complete .env file content as string
    """
    if params is None:
        params = {}
        
    env_content = "# =============================================================================\\n"
    env_content += "# Azure AI Environment Configuration\\n"
    env_content += "# =============================================================================\\n"
    env_content += f"# Generated from Azure AI deployment: {deployment_id[:8]}\\n"
    env_content += f"# Created at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\\n"
    env_content += "# Never commit .env files with real credentials to version control!\\n\\n"
    
    # Azure Subscription & Service Principal
    env_content += "# =============================================================================\\n"
    env_content += "# Azure Subscription & Service Principal\\n"
    env_content += "# =============================================================================\\n"
    if outputs.get("subscription_id"):
        env_content += f'AZURE_SUBSCRIPTION_ID="{outputs["subscription_id"]}"\\n'
    elif params.get("subscription_id"):
        env_content += f'AZURE_SUBSCRIPTION_ID="{params["subscription_id"]}"\\n'
    if outputs.get("tenant_id"):
        env_content += f'AZURE_TENANT_ID="{outputs["tenant_id"]}"\\n'
    if outputs.get("service_principal_app_id"):
        env_content += f'AZURE_CLIENT_ID="{outputs["service_principal_app_id"]}"\\n'
    if outputs.get("service_principal_secret"):
        env_content += f'AZURE_CLIENT_SECRET="{outputs["service_principal_secret"]}"\\n'
    
    # Azure OpenAI Configuration
    env_content += "\\n# =============================================================================\\n"
    env_content += "# Azure OpenAI Configuration\\n"
    env_content += "# =============================================================================\\n"
    if outputs.get("openai_endpoint"):
        env_content += f'AZURE_OPENAI_ENDPOINT="{outputs["openai_endpoint"]}"\\n'
    if outputs.get("azure_openai_key"):
        env_content += f'AZURE_OPENAI_API_KEY="{outputs["azure_openai_key"]}"\\n'
    if outputs.get("openai_deployment_name"):
        env_content += f'AZURE_OPENAI_DEPLOYMENT_NAME="{outputs["openai_deployment_name"]}"\\n'
    # Default API version
    env_content += 'AZURE_OPENAI_API_VERSION="2024-12-01-preview"\\n'
    env_content += 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT="text-embedding-3-small"\\n'
    
    # Azure AI Foundry / AI Studio
    env_content += "\\n# =============================================================================\\n"
    env_content += "# Azure AI Foundry / AI Studio\\n"
    env_content += "# =============================================================================\\n"
    # Use AI inference endpoint for Foundry (different from project URL)
    if outputs.get("ai_inference_endpoint"):
        env_content += f'AI_FOUNDRY_ENDPOINT="{outputs["ai_inference_endpoint"]}"\\n'
    elif outputs.get("azure_foundry_project_url"):
        # Fallback to project URL if inference endpoint not available
        env_content += f'AI_FOUNDRY_ENDPOINT="{outputs["azure_foundry_project_url"]}"\\n'
    # Same key as OpenAI
    if outputs.get("azure_openai_key"):
        env_content += f'AI_FOUNDRY_API_KEY="{outputs["azure_openai_key"]}"\\n'
    # Same deployment name as OpenAI
    if outputs.get("openai_deployment_name"):
        env_content += f'AI_FOUNDRY_DEPLOYMENT_NAME="{outputs["openai_deployment_name"]}"\\n'
    
    # Azure AI Search Configuration
    env_content += "\\n# =============================================================================\\n"
    env_content += "# Azure AI Search Configuration\\n"
    env_content += "# =============================================================================\\n"
    if outputs.get("search_service_endpoint"):
        env_content += f'AZURE_SEARCH_ENDPOINT="{outputs["search_service_endpoint"]}"\\n'
    if outputs.get("azure_search_admin_key"):
        env_content += f'AZURE_SEARCH_API_KEY="{outputs["azure_search_admin_key"]}"\\n'
    # Default index name
    env_content += 'AZURE_SEARCH_INDEX_NAME="ai-search-index"\\n'
    
    # Logging and Monitoring
    env_content += "\\n# =============================================================================\\n"
    env_content += "# Logging and Monitoring (Optional)\\n"
    env_content += "# =============================================================================\\n"
    env_content += 'LOG_LEVEL="INFO"\\n'
    if outputs.get("app_insights_connection_string"):
        env_content += f'APPLICATION_INSIGHTS_CONNECTION_STRING="{outputs["app_insights_connection_string"]}"\\n'
    
    return env_content


def generate_env_filename(deployment_id: str) -> str:
    """Generate standardized filename for .env download.
    
    Args:
        deployment_id: Unique deployment identifier
        
    Returns:
        Filename for the .env file
    """
    return f"azure-ai-{deployment_id[:8]}.env"