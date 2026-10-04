variable "environment" {
  description = "dev or prod"
  type        = string
  default     = "dev"
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be dev or prod"
  }
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus2"
  validation {
    condition     = contains(["eastus2", "westus2", "westeurope"], var.location)
    error_message = "location must be eastus2, westus2 or westeurope"
  }
}

variable "policy_effect" {
  description = "Audit while rolling out, Deny once every AI resource carries its model-card tags"
  type        = string
  default     = "Audit"
  validation {
    condition     = contains(["Audit", "Deny", "Disabled"], var.policy_effect)
    error_message = "policy_effect must be Audit, Deny or Disabled"
  }
}

variable "log_retention_days" {
  description = "Log Analytics retention (30 is the free-retention minimum)"
  type        = number
  default     = 30
}

variable "log_daily_quota_gb" {
  description = "Daily ingestion cap for Log Analytics, so a telemetry bug cannot run up a bill"
  type        = number
  default     = 0.5
}

variable "deploy_drift_alert" {
  description = "Create the scheduled-query alert on drift events (a log alert rule bills per evaluation)"
  type        = bool
  default     = false
}

variable "alert_email" {
  description = "Receives drift alerts; set through a pipeline variable, never committed"
  type        = string
  default     = "model-risk-alerts@example.com"
}

variable "tags" {
  description = "Extra tags merged into the required ones"
  type        = map(string)
  default     = {}
}
