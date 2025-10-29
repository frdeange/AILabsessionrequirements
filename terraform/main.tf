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
# Service Principal for Azure AI deployments
###############################################

# Additional wait time for Service Principal operations
resource "time_sleep" "wait_for_hub_stability" {
  depends_on = [
    azapi_resource.hub,
    time_sleep.wait_project_identities
  ]
  create_duration = "60s"
}

# Create Azure AD Application
resource "azuread_application" "deployment_app" {
  display_name = var.service_principal_name
  description  = "Service Principal for Azure AI deployments"
}

# Create Service Principal
resource "azuread_service_principal" "deployment_sp" {
  client_id = azuread_application.deployment_app.client_id
  app_role_assignment_required = false
  description = "Service Principal for Azure AI deployments"
}

# Create Application Password (Secret)
resource "azuread_application_password" "deployment_secret" {
  application_id = azuread_application.deployment_app.id
  display_name   = "Deployment Secret"
  end_date       = "${var.secret_expiration_date}T23:59:59Z"
}