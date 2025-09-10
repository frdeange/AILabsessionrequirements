variable "rg_name" {
  type = string
}

variable "location" {
  type = string
}

variable "include_search" {
  type    = bool
  default = false
}

variable "storage_account_name" {
  type = string
}

variable "search_service_name" {
  type = string
}

variable "foundry_project_name" {
  type = string
}

variable "key_vault_name" {
  type = string
}

variable "ai_services_name" {
  type = string
}

variable "ai_foundry_hub_name" {
  type = string
}

variable "app_insights_name" {
  type = string
}

variable "log_analytics_workspace_name" {
  type = string
}

variable "subscription_id" {
  type        = string
  description = "(Opcional) Forzar la suscripción usada por el provider azurerm; si vacío se intenta resolución via CLI Azure contexto." 
  default     = ""
}

# --- Model deployment (Azure OpenAI sobre AI Services) ---
variable "enable_model_deployment" {
  type        = bool
  description = "Si true crea el deployment del modelo OpenAI dentro del recurso AI Services"
  default     = true
}

variable "model_deployment_name" {
  type        = string
  description = "Nombre lógico del deployment (p.ej. chat, gpt4)."
  default     = "chat"
}

variable "openai_model_name" {
  type        = string
  description = "Nombre del modelo OpenAI (p.ej. gpt-4.1, gpt-4o)."
  default     = "gpt-4.1"
}

variable "openai_model_version" {
  type        = string
  description = "Versión específica del modelo si aplica; dejar vacío para la más reciente disponible."
  default     = ""
}

variable "openai_deployment_sku" {
  type        = string
  description = "SKU para el deployment (ej: GlobalStandard)."
  default     = "GlobalStandard"
}

variable "rai_policy_name" {
  type        = string
  description = "Nombre de la política Responsible AI (Microsoft.Default si no se personaliza)."
  default     = "Microsoft.Default"
}

variable "assign_storage_rbac" {
  type        = bool
  description = "Si true asigna roles RBAC (Blob Data) a identidades (Hub y AI Services)."
  default     = true
}
