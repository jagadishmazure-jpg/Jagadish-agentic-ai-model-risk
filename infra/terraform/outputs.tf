output "AZURE_RESOURCE_GROUP" {
  value = azurerm_resource_group.this.name
}

output "EVIDENCE_STORAGE_ACCOUNT" {
  value = azurerm_storage_account.evidence.name
}

output "APPLICATIONINSIGHTS_CONNECTION_STRING" {
  value     = azurerm_application_insights.this.connection_string
  sensitive = true
}

output "POLICY_DEFINITION_IDS" {
  value = { for k, v in azurerm_policy_definition.this : k => v.id }
}

output "WORKBOOK_ID" {
  value = azurerm_application_insights_workbook.this.id
}
