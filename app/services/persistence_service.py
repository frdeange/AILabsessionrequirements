"""
Persistence service for Azure AI Multi-Environment Manager.

This service handles all storage operations including deployment state management,
metadata persistence, and the central deployments database.
"""
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Import constants - avoiding circular import
from pathlib import Path

# Constants (copied from main to avoid circular imports)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
TERRAFORM_DIR = BASE_DIR / "terraform"
DEPLOYMENT_STATES_DIR = BASE_DIR / "deployment_states"
DEPLOYMENTS_DB_FILE = DEPLOYMENT_STATES_DIR / "deployments.json"


def load_deployments_db() -> Dict:
    """Load deployments database from persistent storage"""
    try:
        if DEPLOYMENTS_DB_FILE.exists():
            with open(DEPLOYMENTS_DB_FILE, 'r') as f:
                return json.load(f)
        else:
            # Create initial structure
            initial_db = {
                "deployments": {},
                "metadata": {
                    "version": "1.0", 
                    "created": "2025-09-23T09:50:00Z",
                    "description": "Multi-Environment Manager - Deployment Database"
                }
            }
            save_deployments_db(initial_db)
            return initial_db
    except Exception as e:
        print(f"Error loading deployments database: {e}")
        return {"deployments": {}, "metadata": {}}


def save_deployments_db(db: Dict) -> None:
    """Save deployments database to persistent storage"""
    try:
        DEPLOYMENT_STATES_DIR.mkdir(exist_ok=True)
        with open(DEPLOYMENTS_DB_FILE, 'w') as f:
            json.dump(db, f, indent=2)
    except Exception as e:
        print(f"Error saving deployments database: {e}")


def save_deployment_state(deployment_id: str, deployment_data: Dict, outputs: Optional[Dict] = None) -> None:
    """Persist deployment runtime + outputs to disk and index file.

    Args:
        deployment_id: Unique deployment identifier
        deployment_data: Complete deployment state dictionary  
        outputs: Optional outputs dict to override deployment_data['outputs']
    """
    try:
        ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        deployment_dir = DEPLOYMENT_STATES_DIR / deployment_id
        deployment_dir.mkdir(exist_ok=True)

        # Copy terraform state and variables if they exist in shared directory
        terraform_state = TERRAFORM_DIR / "terraform.tfstate"
        if terraform_state.exists():
            shutil.copy(terraform_state, deployment_dir / "terraform.tfstate")

        terraform_tfvars = TERRAFORM_DIR / "terraform.tfvars"
        if terraform_tfvars.exists():
            shutil.copy(terraform_tfvars, deployment_dir / "terraform.tfvars")

        effective_outputs = outputs if outputs is not None else deployment_data.get("outputs", {})

        # Check for terraform state in deployment directory instead of shared directory
        deployment_state = deployment_dir / "terraform.tfstate"
        
        metadata = {
            "deployment_id": deployment_id,
            "deployment_data": deployment_data,
            "outputs": effective_outputs,
            "saved_at": ts,
            "has_state": deployment_state.exists(),
            "status": deployment_data.get("status", "unknown")
        }

        # Save metadata to deployment directory
        with open(deployment_dir / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)

        # Update central deployments database
        db = load_deployments_db()
        db["deployments"][deployment_id] = {
            "id": deployment_id,
            "name": deployment_data.get("params", {}).get("resource_group_base", "Unknown"),
            "status": deployment_data.get("status", "unknown"),
            # Keep first created_at if present, else set now
            "created_at": db.get("deployments", {}).get(deployment_id, {}).get("created_at") or ts,
            "has_state": deployment_state.exists(),
            "outputs_available": bool(effective_outputs),
            "region": deployment_data.get("params", {}).get("location", "unknown"),
            "include_search": deployment_data.get("params", {}).get("include_search", False),
            "resource_names": deployment_data.get("names", {})
        }
        save_deployments_db(db)
    except Exception as e:
        print(f"Error saving deployment state for {deployment_id}: {e}")


def load_deployment_state(deployment_id: str) -> Dict:
    """Load deployment state from persistent storage
    
    Args:
        deployment_id: Unique deployment identifier
        
    Returns:
        Deployment metadata dictionary or empty dict if not found
    """
    try:
        deployment_dir = DEPLOYMENT_STATES_DIR / deployment_id
        if not deployment_dir.exists():
            return {}
        
        metadata_file = deployment_dir / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading deployment state for {deployment_id}: {e}")
        return {}


def get_all_deployments() -> Dict:
    """Get list of all deployments from database
    
    Returns:
        Dictionary of deployment summaries keyed by deployment_id
    """
    db = load_deployments_db()
    return db.get("deployments", {})


def load_all_deployments() -> Dict[str, Dict]:
    """Load all deployments with full state from persistent storage
    
    Returns:
        Dictionary of full deployment data keyed by deployment_id
    """
    deployments = {}
    try:
        db = load_deployments_db()
        for deployment_id in db.get("deployments", {}):
            metadata = load_deployment_state(deployment_id)
            if metadata and "deployment_data" in metadata:
                deployments[deployment_id] = metadata["deployment_data"]
        return deployments
    except Exception as e:
        print(f"Error loading all deployments: {e}")
        return {}


def deployment_exists(deployment_id: str) -> bool:
    """Check if deployment exists in persistent storage
    
    Args:
        deployment_id: Unique deployment identifier
        
    Returns:
        True if deployment exists, False otherwise
    """
    deployment_dir = DEPLOYMENT_STATES_DIR / deployment_id
    return deployment_dir.exists() and (deployment_dir / "metadata.json").exists()


def get_deployment_directory(deployment_id: str) -> Path:
    """Get the directory path for a specific deployment
    
    Args:
        deployment_id: Unique deployment identifier
        
    Returns:
        Path to deployment directory
    """
    return DEPLOYMENT_STATES_DIR / deployment_id


def append_log(deployment_id: str, line: str) -> None:
    """Append a log line to the deployment logs
    
    Args:
        deployment_id: Unique deployment identifier
        line: Log line to append
        
    Note:
        This function works with the global DEPLOYMENTS dict from main.py
        It's a bridge function to maintain compatibility during refactoring
    """
    # Import here to avoid circular import
    from ..main import DEPLOYMENTS
    
    if deployment_id in DEPLOYMENTS:
        DEPLOYMENTS[deployment_id]["logs"].append(line)
    else:
        # If deployment not in memory, we could log to file or ignore
        # For now, we'll just pass since this shouldn't happen in normal flow
        pass


def get_deployment_logs(deployment_id: str) -> list:
    """Get all logs for a deployment
    
    Args:
        deployment_id: Unique deployment identifier
        
    Returns:
        List of log lines
    """
    # Import here to avoid circular import
    from ..main import DEPLOYMENTS
    
    if deployment_id in DEPLOYMENTS:
        return DEPLOYMENTS[deployment_id].get("logs", [])
    else:
        return []