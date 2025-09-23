###############################################
# Azure Storage Account
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
# AI Foundry project connection to Azure Storage Account
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