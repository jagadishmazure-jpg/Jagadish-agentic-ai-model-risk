# Offline plan tests: mocked provider, no Azure credentials, nothing created.
#   terraform init -backend=false && terraform test
mock_provider "azurerm" {
  mock_data "azurerm_client_config" {
    defaults = {
      tenant_id       = "00000000-0000-0000-0000-000000000001"
      subscription_id = "00000000-0000-0000-0000-000000000002"
      object_id       = "00000000-0000-0000-0000-000000000003"
    }
  }
}

run "dev_evidence_plane" {
  command = plan

  variables {
    environment = "dev"
  }

  assert {
    condition     = azurerm_resource_group.this.name == "rg-modelrisk-dev-eus2-001"
    error_message = "resource group must follow the CAF naming pattern"
  }

  assert {
    condition     = length(azurerm_policy_definition.this) == 3 && length(azurerm_resource_group_policy_assignment.this) == 3
    error_message = "three model-risk policy definitions, each assigned"
  }

  assert {
    condition     = contains(jsondecode(azurerm_policy_definition.this["require-model-card-tags"].parameters).tagNames.defaultValue, "model-card-uri")
    error_message = "the tag policy must require model-card-uri"
  }

  assert {
    condition     = jsondecode(azurerm_resource_group_policy_assignment.this["require-model-card-tags"].parameters).effect.value == "Audit"
    error_message = "dev audits first"
  }

  assert {
    condition     = azurerm_log_analytics_workspace.this.sku == "PerGB2018" && azurerm_log_analytics_workspace.this.retention_in_days == 30 && azurerm_log_analytics_workspace.this.daily_quota_gb == 0.5
    error_message = "smallest Log Analytics settings with a daily cap"
  }

  assert {
    condition     = !azurerm_application_insights.this.local_authentication_enabled
    error_message = "App Insights ingestion uses Entra ID, not instrumentation keys"
  }

  assert {
    condition     = azurerm_storage_account.evidence.account_replication_type == "LRS" && azurerm_storage_account.evidence.blob_properties[0].versioning_enabled && !azurerm_storage_account.evidence.shared_access_key_enabled
    error_message = "evidence registry: smallest replication, versioned, keyless"
  }

  assert {
    condition     = length(azurerm_storage_container.evidence) == 3 && alltrue([for c in azurerm_storage_container.evidence : c.container_access_type == "private"])
    error_message = "three private evidence containers"
  }

  assert {
    condition     = length(azurerm_monitor_scheduled_query_rules_alert_v2.drift) == 0
    error_message = "the drift alert bills per evaluation, so dev leaves it off"
  }
}

run "prod_denies_and_alerts" {
  command = plan

  variables {
    environment        = "prod"
    policy_effect      = "Deny"
    deploy_drift_alert = true
  }

  assert {
    condition     = jsondecode(azurerm_resource_group_policy_assignment.this["deny-public-ai-endpoints"].parameters).effect.value == "Deny"
    error_message = "prod denies"
  }

  assert {
    condition     = azurerm_monitor_scheduled_query_rules_alert_v2.drift[0].evaluation_frequency == "PT1H"
    error_message = "drift alert evaluates hourly"
  }
}
