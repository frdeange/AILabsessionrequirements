"""
Naming utilities for Azure resource generation.

This module provides functions for generating Azure-compliant resource names
with appropriate length constraints and random suffixes.
"""
import random
import string
from typing import Dict


def random_suffix(length: int = 5) -> str:
    """Generate a random lowercase suffix of given length."""
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))


def sanitize_base(base: str) -> str:
    """Sanitize base name to only contain lowercase letters and digits."""
    allowed = string.ascii_lowercase + string.digits
    base = base.lower()
    return ''.join(c for c in base if c in allowed)


def build_names(base: str) -> Dict[str, str]:
    """Build resource names with suffix ensuring Azure naming constraints.

    Strategy: truncate base to leave room for 3-char code + suffix.
    
    Args:
        base: Base name for resource group (will be sanitized)
        
    Returns:
        Dictionary with all generated resource names including suffix
    """
    base_s = sanitize_base(base)
    suf = random_suffix()
    
    def compose(limit: int, code: str) -> str:
        """Compose a name within character limit."""
        room_for_base = limit - len(code) - len(suf)
        truncated = base_s[: max(0, room_for_base)]
        return (truncated + code + suf)[:limit]
    
    storage = compose(24, "stg")
    search = compose(60, "src")
    kv = compose(24, "kv")
    ais = compose(40, "ais")
    hub = compose(40, "hub")
    appi = compose(40, "appi")
    project = compose(30, "prj")
    law = compose(40, "law")
    
    return {
        "storage_account_name": storage,
        "search_service_name": search,
        "ai_services_name": ais,
        "ai_foundry_hub_name": hub,
        "app_insights_name": appi,
        "log_analytics_workspace_name": law,
        "project_name": project,
        "suffix": suf,
    }