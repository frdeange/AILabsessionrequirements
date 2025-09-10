
output "storage_blob_url" {
  value = data.azurerm_storage_account.stg.primary_blob_endpoint
}

output "storage_account_name" {
  value = data.azurerm_storage_account.stg.name
}

output "search_service_name" {
  value = var.include_search ? azurerm_search_service.search[0].name : null
}

output "foundry_project_id" {
  value = azurerm_ai_foundry_project.foundry.id
}

output "foundry_project_name" {
  value = azurerm_ai_foundry_project.foundry.name
}

# Endpoint may be exposed via properties; placeholder if attribute available in future provider versions.
output "foundry_project_location" {
  value = azurerm_ai_foundry_project.foundry.location
}

# Attempt to expose Foundry project endpoint (attribute name subject to provider updates)
/* Provider (v4.43.0) no expone todavía endpoint directo del proyecto; output removido */


output "ai_foundry_hub_id" {
  value = azurerm_ai_foundry.hub.id
}

output "ai_foundry_hub_discovery_url" {
  value       = try(azurerm_ai_foundry.hub.discovery_url, null)
  description = "Discovery URL for the AI Foundry Hub (if exposed)."
}

output "ai_services_name" {
  value = azurerm_ai_services.aiservices.name
}

output "ai_services_endpoint" {
  value = try(azurerm_ai_services.aiservices.endpoint, null)
}

output "openai_deployment_id" {
  value = var.enable_model_deployment ? azurerm_cognitive_deployment.model[0].id : null
}

output "openai_deployment_name" {
  value = var.enable_model_deployment ? azurerm_cognitive_deployment.model[0].name : null
}

output "openai_model_name" {
  value = var.openai_model_name
}

output "key_vault_name" {
  value = azurerm_key_vault.kv.name
}

output "app_insights_instrumentation_key" {
  value       = try(azurerm_application_insights.appins.instrumentation_key, null)
  description = "Instrumentation Key (deprecated but sometimes still needed)."
  sensitive   = true
}

output "app_insights_connection_string" {
  value = try(azurerm_application_insights.appins.connection_string, null)
  sensitive = true
}

output "app_insights_app_id" {
  value = try(azurerm_application_insights.appins.app_id, null)
}

# Log Analytics Workspace outputs
output "log_analytics_workspace_id" {
  value = azurerm_log_analytics_workspace.law.id
}

output "log_analytics_workspace_name" {
  value = azurerm_log_analytics_workspace.law.name
}

output "hub_principal_id" {
  value = try(azurerm_ai_foundry.hub.identity[0].principal_id, null)
}

output "ai_services_principal_id" {
  value = try(azurerm_ai_services.aiservices.identity[0].principal_id, null)
}
