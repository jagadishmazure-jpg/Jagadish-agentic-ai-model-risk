# Model risk evidence plane: Azure Policy for model-card tags, Log Analytics + App Insights with a
# model-risk workbook, and a storage account that holds the evidence registry (gate reports,
# scenario results, sign-off audit log). Smallest SKUs; nothing here serves a model.

resource "azurerm_resource_group" "this" {
  name     = "rg-${local.short}-${local.suffix}"
  location = var.location
  tags     = local.tags
}

# --- Azure Policy: definitions from infra/policies/*.json, assigned to the resource group
resource "azurerm_policy_definition" "this" {
  for_each     = local.policies
  name         = "modelrisk-${each.key}"
  policy_type  = "Custom"
  mode         = each.value.mode
  display_name = each.value.displayName
  description  = each.value.description
  metadata     = jsonencode(each.value.metadata)
  parameters   = jsonencode(each.value.parameters)
  policy_rule  = jsonencode(each.value.policyRule)
}

resource "azurerm_resource_group_policy_assignment" "this" {
  for_each             = local.policies
  name                 = "modelrisk-${each.key}"
  resource_group_id    = azurerm_resource_group.this.id
  policy_definition_id = azurerm_policy_definition.this[each.key].id
  parameters           = jsonencode(local.policy_parameters[each.key])
}

# --- Observability: workspace-based Application Insights and the model-risk workbook
resource "azurerm_log_analytics_workspace" "this" {
  name                = "log-${local.short}-${local.suffix}"
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  sku                 = "PerGB2018"
  retention_in_days   = var.log_retention_days
  daily_quota_gb      = var.log_daily_quota_gb
  tags                = local.tags
}

resource "azurerm_application_insights" "this" {
  name                         = "appi-${local.short}-${local.suffix}"
  resource_group_name          = azurerm_resource_group.this.name
  location                     = var.location
  workspace_id                 = azurerm_log_analytics_workspace.this.id
  application_type             = "other"
  local_authentication_enabled = false
  tags                         = local.tags
}

resource "azurerm_application_insights_workbook" "this" {
  name                = uuidv5("dns", "modelrisk-${local.suffix}")
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  display_name        = "Model risk register (${var.environment})"
  source_id           = lower(azurerm_application_insights.this.id)
  category            = "workbook"
  data_json           = file("${path.module}/../workbook/model-risk-workbook.json")
  tags                = local.tags
}

# --- Evidence registry: versioned, keyless storage for gate reports and the audit log
resource "azurerm_storage_account" "evidence" {
  name                            = substr(replace("st${local.short}${var.environment}${local.region}001", "-", ""), 0, 24)
  resource_group_name             = azurerm_resource_group.this.name
  location                        = var.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  shared_access_key_enabled       = false
  allow_nested_items_to_be_public = false
  tags                            = local.tags

  blob_properties {
    versioning_enabled = true
    delete_retention_policy {
      days = 30
    }
    container_delete_retention_policy {
      days = 30
    }
  }
}

resource "azurerm_storage_container" "evidence" {
  for_each              = toset(local.evidence_containers)
  name                  = each.key
  storage_account_id    = azurerm_storage_account.evidence.id
  container_access_type = "private"
}

# Every read, write and delete on the evidence registry lands in Log Analytics.
resource "azurerm_monitor_diagnostic_setting" "evidence_blob" {
  name                       = "diag-evidence-blob"
  target_resource_id         = "${azurerm_storage_account.evidence.id}/blobServices/default"
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id

  enabled_log {
    category = "StorageRead"
  }
  enabled_log {
    category = "StorageWrite"
  }
  enabled_log {
    category = "StorageDelete"
  }
}

# --- Opt-in drift alert on modelrisk.drift events (PSI at or above the alert threshold)
resource "azurerm_monitor_action_group" "drift" {
  count               = var.deploy_drift_alert ? 1 : 0
  name                = "ag-${local.short}-${local.suffix}"
  resource_group_name = azurerm_resource_group.this.name
  short_name          = "modelrisk"
  tags                = local.tags

  email_receiver {
    name                    = "model-risk"
    email_address           = var.alert_email
    use_common_alert_schema = true
  }
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "drift" {
  count                = var.deploy_drift_alert ? 1 : 0
  name                 = "alert-drift-${local.suffix}"
  resource_group_name  = azurerm_resource_group.this.name
  location             = var.location
  scopes               = [azurerm_application_insights.this.id]
  severity             = 2
  evaluation_frequency = "PT1H"
  window_duration      = "PT1H"
  description          = "A model's score PSI reached the alert threshold from its model card."
  tags                 = local.tags

  criteria {
    query                   = "customEvents | where name == 'modelrisk.drift' | where todouble(customDimensions.psi_score) >= 0.25"
    time_aggregation_method = "Count"
    operator                = "GreaterThan"
    threshold               = 0
  }

  action {
    action_groups = [azurerm_monitor_action_group.drift[0].id]
  }
}
