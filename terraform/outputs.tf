
output "storage_blob_url" {
  value = azurerm_storage_account.stg.primary_blob_endpoint
}

output "storage_account_name" {
  value = azurerm_storage_account.stg.name
}

output "search_service_name" {
  value = var.include_search ? azurerm_search_service.search[0].name : null
}

output "foundry_project_id" {
  value = azapi_resource.ai_foundry_project.id
}

output "foundry_project_name" {
  value = azapi_resource.ai_foundry_project.name
}

# Endpoint may be exposed via properties; placeholder if attribute available in future provider versions.
output "foundry_project_location" {
  value = azapi_resource.ai_foundry_project.location
}

# Attempt to expose Foundry project endpoint (attribute name subject to provider updates)
/* Provider (v4.43.0) no expone todavía endpoint directo del proyecto; output removido */


output "ai_foundry_hub_id" {
  value = azapi_resource.hub.id
}

output "ai_foundry_hub_discovery_url" {
  value       = try(azapi_resource.hub.output.properties.endpoint, null)
  description = "Discovery URL for the AI Foundry Hub (if exposed)."
}

output "ai_services_name" {
  value = azapi_resource.hub.name
}

output "ai_services_endpoint" {
  value       = try(azapi_resource.hub.output.properties.endpoint, null)
  description = "Primary Azure AI Services cognitive endpoint (.cognitiveservices.azure.com)."
}

# Derived OpenAI endpoint (same subdomain with .openai.azure.com) – may differ from cognitive endpoint.
output "openai_endpoint" {
  value       = try(replace(azapi_resource.hub.output.properties.endpoint, ".cognitiveservices.azure.com", ".openai.azure.com"), null)
  description = "Derived Azure OpenAI endpoint (.openai.azure.com)."
}

# Derived AI Inference endpoint (preview namespace .services.ai.azure.com)
output "ai_inference_endpoint" {
  value       = try(replace(azapi_resource.hub.output.properties.endpoint, ".cognitiveservices.azure.com", ".services.ai.azure.com"), null)
  description = "Derived Azure AI Inference endpoint (.services.ai.azure.com)."
}

output "openai_deployment_id" {
  value = var.enable_model_deployment ? azurerm_cognitive_deployment.model.id : null
}

output "openai_deployment_name" {
  value = var.enable_model_deployment ? azurerm_cognitive_deployment.model.name : null
}

output "openai_model_name" {
  value = var.openai_model_name
}

# === REQUIRED INFO FOR EXERCISES ===

output "azure_openai_key" {
  value       = data.azurerm_cognitive_account.hub_keys.primary_access_key
  sensitive   = true
  description = "Primary access key for Azure OpenAI"
}

output "azure_search_admin_key" {
  value       = var.include_search ? data.azurerm_search_service.search_keys[0].primary_key : null
  sensitive   = true
  description = "Primary admin key for Azure AI Search"
}

output "azure_foundry_project_url" {
  value       = try(azapi_resource.ai_foundry_project.output.properties.endpoints["AI Foundry API"], null)
  description = "API URL to access the Azure AI Foundry Project"
}

output "search_service_endpoint" {
  # azurerm_search_service does not expose a 'url' attribute; endpoint is deterministic
  value       = var.include_search ? "https://${azurerm_search_service.search[0].name}.search.windows.net" : null
  description = "Primary endpoint of Azure AI Search service (derived)."
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
  value = try(azapi_resource.hub.output.identity.principalId, null)
}

output "ai_foundry_project_principal_id" {
  value = try(azapi_resource.ai_foundry_project.output.identity.principalId, null)
}
