"""
Azure service for Azure AI Multi-Environment Manager.

This service handles all Azure CLI operations including authentication,
subscription management, and retrieval of service credentials.
"""
import json
import os
import subprocess
from typing import Dict, List, Optional, Tuple


def azure_logged_in() -> bool:
    """Return True if 'az account show' succeeds (user logged in)."""
    try:
        subprocess.check_output(["az", "account", "show"], stderr=subprocess.STDOUT)
        return True
    except Exception:
        return False


def attempt_az_login(device_code: bool = False) -> bool:
    """Attempt interactive Azure CLI login.
    
    Args:
        device_code: If True, use device code flow instead of standard login
        
    Returns:
        True if login successful, False otherwise
    """
    cmd = ["az", "login"] + (["--use-device-code"] if device_code else [])
    try:
        subprocess.check_call(cmd)
        return True
    except Exception:
        return False


def list_subscriptions() -> List[dict]:
    """Get list of available Azure subscriptions.
    
    Returns:
        List of subscription dictionaries or empty list if error
    """
    try:
        raw = subprocess.check_output(["az", "account", "list", "--all", "-o", "json"]).decode()
        return json.loads(raw)
    except Exception:
        return []


def auto_pick_subscription(explicit: Optional[str] = None) -> Tuple[Optional[str], str]:
    """Automatically select Azure subscription based on precedence rules.
    
    Order of precedence:
    1. Explicit subscription ID
    2. AZ_SUBSCRIPTION_ID env var  
    3. If only one subscription -> use it
    4. Subscription marked isDefault
    5. First in list
    
    Args:
        explicit: Explicitly provided subscription ID
        
    Returns:
        Tuple of (subscription_id, strategy_description)
    """
    if explicit:
        return explicit, f"explicit({explicit})"
    env_sub = os.getenv("AZ_SUBSCRIPTION_ID")
    if env_sub:
        return env_sub, f"env({env_sub})"
    subs = list_subscriptions()
    if not subs:
        return None, "none-found"
    if len(subs) == 1:
        return subs[0].get("id"), "single"
    # Try default flag
    default_candidates = [s for s in subs if s.get("isDefault")]
    if default_candidates:
        return default_candidates[0].get("id"), "default-flag"
    # Fallback first
    return subs[0].get("id"), "first"


def set_subscription(sub_id: str) -> bool:
    """Set active Azure subscription.
    
    Args:
        sub_id: Subscription ID to set as active
        
    Returns:
        True if successful, False otherwise
    """
    try:
        subprocess.check_call(["az", "account", "set", "--subscription", sub_id])
        return True
    except Exception:
        return False


def get_ai_services_keys(service_name: str, resource_group: str) -> Optional[Dict[str, str]]:
    """Retrieve Azure AI Services (Cognitive Services) API keys.
    
    Args:
        service_name: Name of the AI Services resource
        resource_group: Resource group name
        
    Returns:
        Dictionary with key1 and key2 or None if error
    """
    try:
        ai_keys_raw = subprocess.check_output([
            "az", "cognitiveservices", "account", "keys", "list",
            "-n", service_name,
            "-g", resource_group,
            "-o", "json"
        ])
        ai_keys_json = json.loads(ai_keys_raw.decode())
        if isinstance(ai_keys_json, dict):
            return {
                "key1": ai_keys_json.get("key1"),
                "key2": ai_keys_json.get("key2")
            }
        return None
    except Exception:
        return None


def get_storage_credentials(storage_account_name: str, resource_group: str) -> Optional[Dict[str, str]]:
    """Retrieve Azure Storage account connection string and keys.
    
    Args:
        storage_account_name: Name of the storage account
        resource_group: Resource group name
        
    Returns:
        Dictionary with connection_string and account_key or None if error
    """
    try:
        # Get connection string
        conn_raw = subprocess.check_output([
            "az", "storage", "account", "show-connection-string",
            "-n", storage_account_name,
            "-g", resource_group,
            "-o", "json"
        ])
        conn_json = json.loads(conn_raw.decode())
        connection_string = conn_json.get("connectionString")
        
        # Get account keys
        keys_raw = subprocess.check_output([
            "az", "storage", "account", "keys", "list",
            "-n", storage_account_name,
            "-g", resource_group,
            "-o", "json"
        ])
        keys_json = json.loads(keys_raw.decode())
        account_key = None
        if isinstance(keys_json, list) and keys_json:
            account_key = keys_json[0].get("value")
            
        return {
            "connection_string": connection_string,
            "account_key": account_key
        }
    except Exception:
        return None


def get_search_service_key(search_service_name: str, resource_group: str) -> Optional[Dict[str, str]]:
    """Retrieve Azure AI Search service query key and URL.
    
    Args:
        search_service_name: Name of the search service
        resource_group: Resource group name
        
    Returns:
        Dictionary with search_url and search_key or None if error
    """
    try:
        search_keys_raw = subprocess.check_output([
            "az", "search", "query-key", "list",
            "--service-name", search_service_name,
            "-g", resource_group,
            "-o", "json"
        ])
        search_keys_json = json.loads(search_keys_raw.decode())
        first_key = None
        if isinstance(search_keys_json, list) and search_keys_json:
            first_key = search_keys_json[0].get("key")
            
        search_url = f"https://{search_service_name}.search.windows.net" if first_key else None
        
        return {
            "search_url": search_url,
            "search_key": first_key
        }
    except Exception:
        return None


def ensure_azure_authentication(explicit_subscription: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
    """Ensure Azure CLI is authenticated and subscription is set.
    
    Args:
        explicit_subscription: Optional explicit subscription ID
        
    Returns:
        Tuple of (success, message, chosen_subscription_id)
    """
    # Skip login check if environment variable is set
    if os.getenv("AZ_SKIP_LOGIN_CHECK", "").lower() in {"1", "true", "yes"}:
        return True, "Skipping Azure login check (AZ_SKIP_LOGIN_CHECK set)", None
        
    # Check if logged in
    logged_in = azure_logged_in()
    if not logged_in:
        # Attempt standard login
        if not attempt_az_login(False):
            # Try device code flow as fallback
            if not attempt_az_login(True):
                return False, "Azure CLI login failed (both standard and device code)", None
    
    # Select subscription
    chosen, strategy = auto_pick_subscription(explicit_subscription)
    if not chosen:
        return False, "Could not determine subscription automatically (none available)", None
        
    if set_subscription(chosen):
        return True, f"Subscription set ({strategy}): {chosen}", chosen
    else:
        return False, f"Failed to set subscription ({chosen})", None