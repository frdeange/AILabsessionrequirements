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

variable "openai_account_name" {
  type = string
}

variable "model_deployment_name" {
  type    = string
  default = "gpt-4.1"
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
