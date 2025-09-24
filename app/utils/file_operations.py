"""
File operations utilities for Azure AI Multi-Environment Manager.

This module provides functions for file operations, terraform file management,
and deployment logging.
"""
import shutil
from pathlib import Path
from typing import Dict


def copy_terraform_files(source_dir: Path, dest_dir: Path) -> None:
    """Copy all .tf files from source to destination directory for isolated terraform execution.
    
    Args:
        source_dir: Source directory containing .tf files
        dest_dir: Destination directory for copied files
    """
    # Ensure destination directory exists
    dest_dir.mkdir(exist_ok=True)
    
    # Copy all .tf files
    tf_files = source_dir.glob("*.tf")
    for tf_file in tf_files:
        shutil.copy2(tf_file, dest_dir / tf_file.name)


def cleanup_terraform_files(deployment_dir: Path) -> None:
    """Remove .tf files from deployment directory after successful operations.
    
    Keeps only terraform.tfstate and terraform.tfvars files for potential future operations.
    
    Args:
        deployment_dir: Directory to clean up
    """
    tf_files = deployment_dir.glob("*.tf")
    for tf_file in tf_files:
        if tf_file.exists():
            tf_file.unlink()


# Note: append_log function moved back to main.py temporarily to avoid circular imports
# Will be refactored properly in later phases when we create proper logging service