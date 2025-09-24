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
# RBAC for Hub MSI (AI Foundry Hub Identity)
###############################################

# Storage Blob Data Contributor for AI Foundry Hub
resource "azurerm_role_assignment" "storage_blob_data_contributor_hub" {
  depends_on = [
    time_sleep.wait_project_identities
  ]
  scope                = azurerm_storage_account.stg.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azapi_resource.hub.output.identity.principalId
}

# Search Index Data Contributor for AI Foundry Hub (conditional)
resource "azurerm_role_assignment" "search_index_data_contributor_hub" {
  count = var.include_search ? 1 : 0
  depends_on = [
    time_sleep.wait_project_identities
  ]
  scope                = azurerm_search_service.search[0].id
  role_definition_name = "Search Index Data Contributor"
  principal_id         = azapi_resource.hub.output.identity.principalId
}

# Search Service Contributor for AI Foundry Hub (conditional)
resource "azurerm_role_assignment" "search_service_contributor_hub" {
  count = var.include_search ? 1 : 0
  depends_on = [
    time_sleep.wait_project_identities
  ]
  scope                = azurerm_search_service.search[0].id
  role_definition_name = "Search Service Contributor"
  principal_id         = azapi_resource.hub.output.identity.principalId
}

###############################################
# RBAC for Current User
###############################################

# Storage Blob Data Contributor for current user
resource "azurerm_role_assignment" "storage_blob_data_contributor_current_user" {
  depends_on = [
    time_sleep.wait_project_identities
  ]
  scope                = azurerm_storage_account.stg.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}

# Azure AI Developer for current user
resource "azurerm_role_assignment" "ai_developer_current_user" {
  depends_on = [
    time_sleep.wait_project_identities
  ]
  scope                = azapi_resource.hub.id
  role_definition_name = "Azure AI Developer"
  principal_id         = data.azurerm_client_config.current.object_id
}

# Search Index Data Contributor for current user (conditional)
resource "azurerm_role_assignment" "search_index_data_contributor_current_user" {
  count = var.include_search ? 1 : 0
  depends_on = [
    time_sleep.wait_project_identities
  ]
  scope                = azurerm_search_service.search[0].id
  role_definition_name = "Search Index Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}

# Search Service Contributor for current user (conditional)
resource "azurerm_role_assignment" "search_service_contributor_current_user" {
  count = var.include_search ? 1 : 0
  depends_on = [
    time_sleep.wait_project_identities
  ]
  scope                = azurerm_search_service.search[0].id
  role_definition_name = "Search Service Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}

###############################################
# RBAC for Service Principal
###############################################

###############################################
# RBAC for Azure AI Search Service Managed Identity (new)
###############################################

# Grant the Search service managed identity permissions over the Storage Account so that
# indexers / enrichment pipelines can both read and write artifacts (blob + possible skill outputs).
# Using Contributor level for blobs (as requested) to avoid permission friction during workshops.
resource "azurerm_role_assignment" "storage_blob_data_contributor_search_mi" {
  count = var.include_search ? 1 : 0
  depends_on = [
    azurerm_search_service.search
  ]
  scope                = azurerm_storage_account.stg.id
  role_definition_name = "Storage Blob Data Contributor"
  # identity is a list in the schema; use first (only) element
  principal_id         = azurerm_search_service.search[0].identity[0].principal_id
}

# Storage Blob Data Contributor for Service Principal
resource "azurerm_role_assignment" "storage_blob_data_contributor_sp" {
  depends_on = [
    azapi_resource.hub,
    time_sleep.wait_for_hub_stability
  ]
  scope                = azurerm_storage_account.stg.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azuread_service_principal.workshop_sp.object_id
}

# Search Index Data Contributor for Service Principal (conditional)
resource "azurerm_role_assignment" "search_index_data_contributor_sp" {
  count = var.include_search ? 1 : 0
  depends_on = [
    azapi_resource.hub,
    time_sleep.wait_for_hub_stability
  ]
  scope                = azurerm_search_service.search[0].id
  role_definition_name = "Search Index Data Contributor"
  principal_id         = azuread_service_principal.workshop_sp.object_id
}

# Search Service Contributor for Service Principal (conditional)
resource "azurerm_role_assignment" "search_service_contributor_sp" {
  count = var.include_search ? 1 : 0
  depends_on = [
    azapi_resource.hub,
    time_sleep.wait_for_hub_stability
  ]
  scope                = azurerm_search_service.search[0].id
  role_definition_name = "Search Service Contributor"
  principal_id         = azuread_service_principal.workshop_sp.object_id
}

# Application Insights Reader for Service Principal
resource "azurerm_role_assignment" "app_insights_reader_sp" {
  depends_on = [
    azapi_resource.hub,
    time_sleep.wait_for_hub_stability
  ]
  scope                = azurerm_application_insights.appins.id
  role_definition_name = "Application Insights Reader"
  principal_id         = azuread_service_principal.workshop_sp.object_id
}

# Role assignment: Azure AI Project Manager
resource "azurerm_role_assignment" "sp_ai_project_manager" {
  depends_on = [
    azapi_resource.hub,
    time_sleep.wait_for_hub_stability
  ]
  scope                = azapi_resource.hub.id
  role_definition_id   = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/eadc314b-1a2d-4efa-be10-5d325db5065e"
  principal_id         = azuread_service_principal.workshop_sp.object_id
}

# Role assignment: Azure AI User
resource "azurerm_role_assignment" "sp_ai_user" {
  depends_on = [
    azapi_resource.hub,
    time_sleep.wait_for_hub_stability
  ]
  scope                = azapi_resource.hub.id
  role_definition_id   = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/53ca6127-db72-4b80-b1b0-d745d6d5456d"
  principal_id         = azuread_service_principal.workshop_sp.object_id
}

# Role assignment: Cognitive Services Data Contributor (Preview)
resource "azurerm_role_assignment" "sp_cognitive_services_data_contributor" {
  depends_on = [
    azapi_resource.hub,
    time_sleep.wait_for_hub_stability
  ]
  scope                = azapi_resource.hub.id
  role_definition_id   = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/19c28022-e58e-450d-a464-0b2a53034789"
  principal_id         = azuread_service_principal.workshop_sp.object_id
}