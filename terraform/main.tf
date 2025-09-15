###############################################
# Core data sources
###############################################
data "azurerm_client_config" "current" {}

# Data source to access AI Services keys after creation
data "azurerm_cognitive_account" "hub_keys" {
  name                = azapi_resource.hub.name
  resource_group_name = azurerm_resource_group.rg.name
  depends_on         = [azapi_resource.hub]
}

# Data source to access Search Service keys (conditional)
data "azurerm_search_service" "search_keys" {
  count               = var.include_search ? 1 : 0
  name                = azurerm_search_service.search[0].name
  resource_group_name = azurerm_resource_group.rg.name
  depends_on         = [azurerm_search_service.search]
}

###############################################
# Resource Group
###############################################
resource "azurerm_resource_group" "rg" {
  name     = var.rg_name
  location = var.location
}

###############################################
# Application Insights
###############################################
resource "azurerm_log_analytics_workspace" "law" {
  name                = var.log_analytics_workspace_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_application_insights" "appins" {
  name                = var.app_insights_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  application_type    = "web"
  workspace_id        = azurerm_log_analytics_workspace.law.id
  # Evitar errores intermitentes en la actualización de billing features
  lifecycle { ignore_changes = [daily_data_cap_in_gb, daily_data_cap_notifications_disabled] }
  timeouts { create = "10m" }
}

###############################################
# Create the Azure Storage
###############################################

resource "azurerm_storage_account" "stg" {
  name                = var.storage_account_name
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location

  account_kind             = "StorageV2"
  account_tier             = "Standard"
  account_replication_type = "LRS"

  ## Identity configuration
  shared_access_key_enabled = false

  ## Network access configuration
  allow_nested_items_to_be_public = false
  network_rules {
    default_action = "Allow"
    bypass = [
      "AzureServices"
    ]
  }
}

###############################################
# Create the AI Foundry resource
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
# Create a deployment for OpenAI's in the AI Foundry Resource
###############################################

resource "azurerm_cognitive_deployment" "model" {
  depends_on = [
    azapi_resource.hub
  ]

  name = var.model_deployment_name != "" ? var.model_deployment_name : var.openai_model_name
  cognitive_account_id = azapi_resource.hub.id

  sku {
    name     = var.openai_deployment_sku
    capacity = 1
  }

  model {
    format  = "OpenAI"
    name    = var.openai_model_name
    version = var.openai_model_version == "" ? null : var.openai_model_version
  }
}

###############################################
# Create a Foundry Project
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

###############################################
# (Optional) Azure AI Search
###############################################
resource "azurerm_search_service" "search" {
  count               = var.include_search ? 1 : 0
  name                = var.search_service_name
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "basic"
  replica_count       = 1
  partition_count     = 1
  hosting_mode        = "default"
}

###############################################
# Create the AI Foundry project connection to Azure Storage Account
###############################################
resource "azapi_resource" "conn_storage" {
  type                      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01"
  name                      = azurerm_storage_account.stg.name
  parent_id                 = azapi_resource.ai_foundry_project.id
  schema_validation_enabled = false

  depends_on = [
    azapi_resource.ai_foundry_project
  ]

  body = {
    name = azurerm_storage_account.stg.name
    properties = {
      category = "AzureStorageAccount"
      target   = azurerm_storage_account.stg.primary_blob_endpoint
      authType = "AAD"
      metadata = {
        ApiType    = "Azure"
        ResourceId = azurerm_storage_account.stg.id
        location   = var.location
      }
    }
  }

  response_export_values = [
    "identity.principalId"
  ]
}

###############################################
# Create the AI Foundry project connection to AI Search
###############################################
resource "azapi_resource" "conn_aisearch" {
  count                     = var.include_search ? 1 : 0
  type                      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01"
  name                      = azurerm_search_service.search[0].name
  parent_id                 = azapi_resource.ai_foundry_project.id
  schema_validation_enabled = false

  depends_on = [
    azapi_resource.ai_foundry_project
  ]

  body = {
    name = azurerm_search_service.search[0].name
    properties = {
      category = "CognitiveSearch"
      target   = "https://${azurerm_search_service.search[0].name}.search.windows.net"
      authType = "AAD"
      metadata = {
        ApiType    = "Azure"
        ApiVersion = "2025-05-01-preview"
        ResourceId = azurerm_search_service.search[0].id
        location   = var.location
      }
    }
  }

  response_export_values = [
    "identity.principalId"
  ]
}

###############################################
# RBAC role assignments (following Microsoft patterns)
###############################################

# Wait for project identity to be created and replicated
resource "time_sleep" "wait_project_identities" {
  depends_on = [
    azapi_resource.ai_foundry_project
  ]
  create_duration = "10s"
}

# Storage Blob Data Contributor for AI Foundry Project
resource "azurerm_role_assignment" "storage_blob_data_contributor_ai_foundry_project" {
  depends_on = [
    time_sleep.wait_project_identities
  ]
  scope                = azurerm_storage_account.stg.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azapi_resource.ai_foundry_project.output.identity.principalId
}

# Search Index Data Contributor for AI Foundry Project (conditional)
resource "azurerm_role_assignment" "search_index_data_contributor_ai_foundry_project" {
  count = var.include_search ? 1 : 0
  depends_on = [
    time_sleep.wait_project_identities
  ]
  scope                = azurerm_search_service.search[0].id
  role_definition_name = "Search Index Data Contributor"
  principal_id         = azapi_resource.ai_foundry_project.output.identity.principalId
}

# Search Service Contributor for AI Foundry Project (conditional)
resource "azurerm_role_assignment" "search_service_contributor_ai_foundry_project" {
  count = var.include_search ? 1 : 0
  depends_on = [
    time_sleep.wait_project_identities
  ]
  scope                = azurerm_search_service.search[0].id
  role_definition_name = "Search Service Contributor"
  principal_id         = azapi_resource.ai_foundry_project.output.identity.principalId
}

###############################################
# Service Principal for workshops
###############################################

# Create Azure AD Application
resource "azuread_application" "workshop_app" {
  display_name = var.service_principal_name
  description  = "Service Principal for Azure AI workshop exercises"
}

# Create Service Principal
resource "azuread_service_principal" "workshop_sp" {
  client_id = azuread_application.workshop_app.client_id
  app_role_assignment_required = false
  description = "Service Principal for Azure AI workshop exercises"
}

# Create Application Password (Secret)
resource "azuread_application_password" "workshop_secret" {
  application_id = azuread_application.workshop_app.id
  display_name   = "Workshop Secret"
  end_date       = "${var.secret_expiration_date}T23:59:59Z"
}

# Role assignment: Azure AI Project Manager
resource "azurerm_role_assignment" "sp_ai_project_manager" {
  depends_on = [
    azapi_resource.hub
  ]
  scope                = azapi_resource.hub.id
  role_definition_id   = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/b78c784d-1c93-4b78-8810-3c7f7bb8f11f"
  principal_id         = azuread_service_principal.workshop_sp.object_id
}

# Role assignment: Azure AI User
resource "azurerm_role_assignment" "sp_ai_user" {
  depends_on = [
    azapi_resource.hub
  ]
  scope                = azapi_resource.hub.id
  role_definition_id   = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/1415e2d3-7a32-4b93-b4d1-bb3eb63b5c5b"
  principal_id         = azuread_service_principal.workshop_sp.object_id
}

# Role assignment: Cognitive Services Data Contributor
resource "azurerm_role_assignment" "sp_cognitive_services_data_contributor" {
  depends_on = [
    azapi_resource.hub
  ]
  scope                = azapi_resource.hub.id
  role_definition_id   = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/25fbc0a9-bd7c-42a3-aa1a-3b75d497ee68"
  principal_id         = azuread_service_principal.workshop_sp.object_id
}