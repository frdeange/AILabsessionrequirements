"""
Request validation service for deployment forms and parameters.

Handles validation of user inputs, form data, and deployment parameters.
"""
from typing import Optional, Dict, Any, Tuple
from fastapi import Request
from fastapi.templating import Jinja2Templates

from ..config import (
    ALLOWED_MODEL_NAMES, 
    MIN_RESOURCE_GROUP_LENGTH, 
    MAX_RESOURCE_GROUP_LENGTH
)
from ..utils.naming import sanitize_base


def validate_deployment_form(
    resource_group_base: str,
    location: str,
    openai_model_name: str,
    service_principal_name: str,
    secret_expiration_date: str,
    include_search: Optional[str] = None,
    subscription_id: Optional[str] = None
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """Validate deployment form parameters.
    
    Args:
        resource_group_base: Base name for resource group
        location: Azure region
        openai_model_name: Selected OpenAI model
        service_principal_name: Name for service principal
        secret_expiration_date: Expiration date for SP secret
        include_search: Optional search service flag
        subscription_id: Optional Azure subscription ID
        
    Returns:
        Tuple of (is_valid, error_message, validated_params)
    """
    # Validate resource group base
    base_clean = sanitize_base(resource_group_base)
    if len(base_clean) < MIN_RESOURCE_GROUP_LENGTH:
        return False, "Resource group base too short.", None
    if len(base_clean) > MAX_RESOURCE_GROUP_LENGTH:
        return False, f"Resource group base too long (max {MAX_RESOURCE_GROUP_LENGTH}).", None

    # Validate model selection
    if openai_model_name not in ALLOWED_MODEL_NAMES:
        return False, "Invalid model selection.", None
    
    # Validate required fields
    if not service_principal_name.strip():
        return False, "Service principal name is required.", None
        
    if not secret_expiration_date.strip():
        return False, "Secret expiration date is required.", None
    
    # Process search flag
    include_search_flag = str(include_search).lower() in {"on", "1", "true", "yes"}
    
    # Build validated parameters
    validated_params = {
        "resource_group_base_clean": base_clean,
        "location": location,
        "include_search": include_search_flag,
        "openai_model_name": openai_model_name,
        "service_principal_name": service_principal_name.strip(),
        "secret_expiration_date": secret_expiration_date.strip(),
        "subscription_id": (subscription_id or "").strip()
    }
    
    return True, None, validated_params


def render_form_error(
    templates: Jinja2Templates, 
    request: Request, 
    error_message: str
) -> Any:
    """Render index template with error message.
    
    Args:
        templates: Jinja2Templates instance
        request: FastAPI request object
        error_message: Error message to display
        
    Returns:
        Template response with error
    """
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "error": error_message}
    )