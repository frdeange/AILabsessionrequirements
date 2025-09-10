resource "azurerm_resource_group" "rg" {
  name     = var.rg_name
  location = var.location
}

resource "azurerm_storage_account" "stg" {
  name                            = var.storage_account_name
  resource_group_name             = azurerm_resource_group.rg.name
  location                        = azurerm_resource_group.rg.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  allow_nested_items_to_be_public = false
}

# Azure OpenAI (Cognitive Services) account
resource "azurerm_cognitive_account" "openai" {
  name                  = var.openai_account_name
  resource_group_name   = azurerm_resource_group.rg.name
  location              = azurerm_resource_group.rg.location
  kind                  = "OpenAI"
  sku_name              = "S0"
  custom_subdomain_name = var.openai_account_name
  lifecycle {
    ignore_changes = [tags]
  }
  # Tags can be extended
  tags = {
    env = "demo"
  }
}

# Cognitive model deployment (Terraform-managed)
resource "azurerm_cognitive_deployment" "openai_deployment" {
  name                 = var.model_deployment_name
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = var.model_deployment_name # e.g. gpt-4.1
                # adjust if specific version needed
  }

  sku {
    name = "S0"
  }

  depends_on = [azurerm_cognitive_account.openai]
}

# Conditional Azure AI Search service
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

# Azure AI Foundry Project (managed by Terraform)
resource "azurerm_key_vault" "kv" {
  name                       = var.key_vault_name
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  purge_protection_enabled   = true
  soft_delete_retention_days = 7
}

resource "azurerm_key_vault_access_policy" "kv_policy" {
  key_vault_id = azurerm_key_vault.kv.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  key_permissions = ["Create", "Get", "Delete", "Purge", "GetRotationPolicy"]
  secret_permissions = ["Get", "Set", "Delete", "Purge"]
}

resource "azurerm_ai_services" "aiservices" {
  name                = var.ai_services_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku_name            = "S0"
}

resource "azurerm_ai_foundry" "hub" {
  name                = var.ai_foundry_hub_name
  location            = azurerm_ai_services.aiservices.location
  resource_group_name = azurerm_resource_group.rg.name
  storage_account_id  = azurerm_storage_account.stg.id
  key_vault_id        = azurerm_key_vault.kv.id
  application_insights_id = azurerm_application_insights.appins.id

  identity { type = "SystemAssigned" }
}

resource "azurerm_ai_foundry_project" "foundry" {
  name               = var.foundry_project_name
  location           = azurerm_ai_foundry.hub.location
  ai_services_hub_id = azurerm_ai_foundry.hub.id

  description = "Provisioned via FastAPI + Terraform demo"

  tags = {
    env = "demo"
  }
}

# Application Insights (observability for hub/project usage)
resource "azurerm_application_insights" "appins" {
  name                = var.app_insights_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  application_type    = "web"
}
