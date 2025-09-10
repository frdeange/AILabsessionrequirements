output "openai_endpoint" {
  value = azurerm_cognitive_account.openai.properties["endpoint"]
}

# Primary key (OpenAI) - accessible via listKeys data source; using az cli later for safety.
# Provide placeholder output by referencing account id (for subsequent CLI call in app if needed)
output "openai_account_id" {
  value = azurerm_cognitive_account.openai.id
}

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
output "foundry_project_endpoint" {
  value       = try(azurerm_ai_foundry_project.foundry.endpoint, null)
  description = "Foundry project endpoint if exposed by provider; may be null if not yet supported."
}

output "openai_deployment_id" {
  value = azurerm_cognitive_deployment.openai_deployment.id
}

output "openai_deployment_name" {
  value = azurerm_cognitive_deployment.openai_deployment.name
}

output "deployment_name" {
  value = var.model_deployment_name
}
