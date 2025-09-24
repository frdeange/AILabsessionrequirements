"""
Configuration settings for Azure AI Multi-Environment Manager.

Contains application configuration, constants, and environment settings.
"""
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Directory configuration
BASE_DIR = Path(__file__).resolve().parent.parent  # Go up to project root
TERRAFORM_DIR = BASE_DIR / "terraform"
DEPLOYMENT_STATES_DIR = BASE_DIR / "deployment_states"
DEPLOYMENTS_DB_FILE = DEPLOYMENT_STATES_DIR / "deployments.json"

# Application configuration
APP_TITLE = "Azure AI Provisioner"
STATIC_DIR = BASE_DIR / "app" / "static"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"

# Model configuration
ALLOWED_MODEL_NAMES = {"gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini"}

# Default deployment parameters
DEFAULT_MODEL_VERSION = ""  # omit to let platform choose
DEFAULT_DEPLOYMENT_SKU = "GlobalStandard"
DEFAULT_MODEL_DEPLOYMENT_ENABLED = True

# Resource group name limits
MIN_RESOURCE_GROUP_LENGTH = 3
MAX_RESOURCE_GROUP_LENGTH = 15

# WebSocket update interval (seconds)
WEBSOCKET_UPDATE_INTERVAL = 1