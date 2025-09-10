terraform {
  # Terraform core version (changed from invalid '>= 4.30.0').
  # Choose a baseline compatible with azurerm provider 4.x (Terraform 1.6+ recommended).
  required_version = ">= 1.13.1"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 4.39.0"
    }
  }
}

provider "azurerm" {
  features {}
}
