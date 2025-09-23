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
# AI Foundry project connection to AI Search
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