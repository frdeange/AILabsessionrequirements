###############################################
# Core data sources
###############################################
data "azurerm_client_config" "current" {}

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
# Key Vault (explicit for control & future secrets)
###############################################
resource "azurerm_key_vault" "kv" {
  name                       = var.key_vault_name
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
}

resource "azurerm_key_vault_access_policy" "kv_policy" {
  key_vault_id = azurerm_key_vault.kv.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  key_permissions    = ["Create", "Get", "Delete", "Purge", "GetRotationPolicy"]
  secret_permissions = ["Get", "Set", "Delete", "Purge"]
}

###############################################
# Azure AI Services (base for Foundry Hub)
###############################################
resource "azurerm_ai_services" "aiservices" {
  name                = var.ai_services_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku_name            = "S0"
  custom_subdomain_name = var.ai_services_name
  identity { type = "SystemAssigned" }
}

###############################################
# Storage Account via AzAPI (avoid data plane polling with keys)
###############################################

resource "azapi_resource" "stg" {
  type      = "Microsoft.Storage/storageAccounts@2023-01-01"
  name      = var.storage_account_name
  parent_id = azurerm_resource_group.rg.id
  location  = azurerm_resource_group.rg.location
  body = {
    sku = {
      name = "Standard_LRS"
    }
    kind = "StorageV2"
    properties = {
      publicNetworkAccess          = "Enabled"
      minimumTlsVersion            = "TLS1_2"
      allowBlobPublicAccess        = false
      allowSharedKeyAccess         = false
      largeFileSharesState         = "Enabled"
      defaultToOAuthAuthentication = true
    }
  }
  response_export_values = ["id"]
}

data "azurerm_storage_account" "stg" {
  name                = var.storage_account_name
  resource_group_name = azurerm_resource_group.rg.name
  depends_on          = [azapi_resource.stg]
}

###############################################
# RBAC assignments (condicionales)
###############################################
resource "azurerm_role_assignment" "hub_blob_contributor" {
  count                = var.assign_storage_rbac ? 1 : 0
  scope                = azurerm_resource_group.rg.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_ai_foundry.hub.identity[0].principal_id
  depends_on           = [azurerm_ai_foundry.hub]
}

resource "azurerm_role_assignment" "aiservices_blob_reader" {
  count                = var.assign_storage_rbac ? 1 : 0
  scope                = data.azurerm_storage_account.stg.id
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = azurerm_ai_services.aiservices.identity[0].principal_id
  depends_on           = [azurerm_ai_services.aiservices]
}


resource "azurerm_role_assignment" "current_user_blob_contributor" {
  count                = var.assign_storage_rbac ? 1 : 0
  scope                = data.azurerm_storage_account.stg.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
  depends_on           = [azapi_resource.stg]
}

###############################################
# Azure AI Foundry Hub
###############################################
resource "azurerm_ai_foundry" "hub" {
  name                    = var.ai_foundry_hub_name
  location                = azurerm_ai_services.aiservices.location
  resource_group_name     = azurerm_resource_group.rg.name
  storage_account_id      = data.azurerm_storage_account.stg.id
  key_vault_id            = azurerm_key_vault.kv.id
  application_insights_id = azurerm_application_insights.appins.id

  identity { type = "SystemAssigned" }
}

###############################################
# Azure AI Foundry Project
###############################################
resource "azurerm_ai_foundry_project" "foundry" {
  name               = var.foundry_project_name
  location           = azurerm_ai_foundry.hub.location
  ai_services_hub_id = azurerm_ai_foundry.hub.id

  description = "Provisioned via FastAPI + Terraform demo"

  tags = { env = "demo" }
  depends_on = [time_sleep.after_rbac]
  identity { type = "SystemAssigned" }
}

resource "time_sleep" "after_rbac" {
  create_duration = "120s"
  depends_on = [
    azurerm_role_assignment.hub_blob_contributor,
    azurerm_role_assignment.aiservices_blob_reader,
    azurerm_role_assignment.current_user_blob_contributor
  ]
}


###############################################
# OpenAI model deployment (sobre AI Services) opcional
###############################################
resource "azurerm_cognitive_deployment" "model" {
  count                = var.enable_model_deployment ? 1 : 0
  name                 = var.model_deployment_name
  cognitive_account_id = azurerm_ai_services.aiservices.id
  rai_policy_name      = var.rai_policy_name

  model {
    format  = "OpenAI"
    name    = var.openai_model_name
    version = var.openai_model_version == "" ? null : var.openai_model_version
  }

  sku { name = var.openai_deployment_sku }

  depends_on = [azurerm_ai_foundry_project.foundry]
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


