###############################################
# Azure AI Foundry Hub (AI Services)
###############################################

resource "azapi_resource" "hub" {

  type                      = "Microsoft.CognitiveServices/accounts@2025-04-01-preview"
  name                      = var.ai_services_name
  parent_id                 = azurerm_resource_group.rg.id
  location                  = azurerm_resource_group.rg.location
  schema_validation_enabled = false

  body = {
    
    kind = "AIServices"
    sku = {
      name = "S0"
    }
    identity = {
      type = "SystemAssigned"
    }

    properties = {
      # Support both Entra ID and API Key authentication for Cognitive Services account
      disableLocalAuth = false

      # Specifies that this is an AI Foundry resource
      allowProjectManagement = true
      
      # Required: Custom subdomain name for DNS names created for this Foundry
      customSubDomainName = var.ai_services_name
    }
  }
}

###############################################
# OpenAI Model Deployment in AI Foundry Hub
###############################################

resource "azurerm_cognitive_deployment" "model" {
  depends_on = [
    azapi_resource.hub
  ]

  name = var.model_deployment_name != "" ? var.model_deployment_name : var.openai_model_name
  cognitive_account_id = azapi_resource.hub.id

  sku {
    name     = var.openai_deployment_sku
    capacity = 500
  }

  model {
    format  = "OpenAI"
    name    = var.openai_model_name
    version = var.openai_model_version == "" ? null : var.openai_model_version
  }
}

###############################################
# Azure AI Foundry Project
###############################################

resource "azapi_resource" "ai_foundry_project" {
  type                      = "Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview"
  name                      = var.foundry_project_name
  parent_id                 = azapi_resource.hub.id
  location                  = azapi_resource.hub.location
  schema_validation_enabled = false

  body = {
    sku = {
      name = "S0"
    }
    identity = {
      type = "SystemAssigned"
    }

    properties = {
      displayName = var.foundry_project_name
      description = "Provisioned via FastAPI + Terraform demo"
    }
  }
}