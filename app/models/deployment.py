"""
Data models and types for Azure AI Multi-Environment Manager.

This module defines the core data structures, enums, and constants used
throughout the application for type safety and documentation.
"""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class DeploymentStatus(Enum):
    """Possible states of a deployment."""
    TERRAFORM = "terraform"
    FOUNDRY = "foundry"
    COMPLETED = "completed"
    DESTROYING = "destroying"
    DESTROYED = "destroyed"
    ERROR = "error"
    DESTROY_ERROR = "destroy_error"


@dataclass
class ResourceNames:
    """Generated Azure resource names for a deployment."""
    storage_account_name: str
    search_service_name: str
    ai_services_name: str
    ai_foundry_hub_name: str
    app_insights_name: str
    log_analytics_workspace_name: str
    project_name: str
    suffix: str


@dataclass
class DeploymentParams:
    """Parameters for creating a new deployment."""
    resource_group_base: str
    location: str
    include_search: bool
    enable_model_deployment: bool
    model_deployment_name: str
    openai_model_name: str
    openai_model_version: str
    openai_deployment_sku: str
    service_principal_name: str
    secret_expiration_date: str
    subscription_id: Optional[str] = None


@dataclass
class DeploymentState:
    """Complete state of a deployment."""
    id: str
    name: str
    status: DeploymentStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    has_state: bool = False
    outputs_available: bool = False
    region: str = ""
    include_search: bool = False
    params: Optional[DeploymentParams] = None
    names: Optional[ResourceNames] = None
    outputs: Dict = None
    logs: List[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        """Initialize mutable defaults."""
        if self.outputs is None:
            self.outputs = {}
        if self.logs is None:
            self.logs = []


# Application constants
TERRAFORM_FILE_EXTENSIONS = [".tf"]
DEPLOYMENT_REQUIRED_FILES = ["terraform.tfstate", "terraform.tfvars", "metadata.json"]
AZURE_RESOURCE_LIMITS = {
    "storage_account_name": 24,
    "search_service_name": 60,
    "ai_services_name": 40,
    "ai_foundry_hub_name": 40,
    "app_insights_name": 40,
    "log_analytics_workspace_name": 40,
    "project_name": 30,
}

# Environment file format constants
ENV_SECTIONS = {
    "azure_openai": [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY_PRIMARY", 
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_DEPLOYMENT_NAME",
    ],
    "ai_foundry": [
        "AI_FOUNDRY_PROJECT_ENDPOINT",
        "AI_FOUNDRY_API_KEY_PRIMARY",
        "AI_FOUNDRY_API_VERSION", 
        "AI_FOUNDRY_DEPLOYMENT_NAME",
    ],
    "azure_search": [
        "AZURE_SEARCH_URL",
        "AZURE_SEARCH_KEY", 
        "AZURE_SEARCH_INDEX_NAME",
    ],
    "storage": [
        "AZURE_STORAGE_CONNECTION_STRING",
    ],
}

# Default fixed values for environment files
ENV_FIXED_VALUES = {
    "AZURE_OPENAI_API_VERSION": "2024-12-01-preview",
    "AI_FOUNDRY_API_VERSION": "2024-12-01-preview", 
    "AZURE_SEARCH_INDEX_NAME": "ai-search-index",
}