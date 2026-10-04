// Model risk evidence plane (Bicep twin of infra/terraform): policy definitions at subscription
// scope, then a resource group with policy assignments, Log Analytics, workspace-based
// Application Insights, the model-risk workbook and the evidence registry storage account.
targetScope = 'subscription'

@allowed(['dev', 'prod'])
param environment string = 'dev'
@allowed(['eastus2', 'westus2', 'westeurope'])
param location string = 'eastus2'
@allowed(['Audit', 'Deny', 'Disabled'])
param policyEffect string = 'Audit'
@description('Log Analytics retention in days (30 is the free-retention minimum)')
param logRetentionDays int = 30
@description('Creates the hourly drift alert (a log alert rule bills per evaluation)')
param deployDriftAlert bool = false
@description('Receives drift alerts; pass it at deploy time, never commit a real address')
param alertEmail string = 'model-risk-alerts@example.com'

var region = { eastus2: 'eus2', westus2: 'wus2', westeurope: 'weu' }[location]
var suffix = '${environment}-${region}-001'
var tags = {
  env: environment
  owner: 'model-risk-management'
  app: 'agentic-ai-model-risk'
  'cost-center': 'CC-7100'
  'managed-by': 'bicep'
}

module policies 'modules/policies.bicep' = {
  name: 'modelrisk-policies'
}

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-modelrisk-${suffix}'
  location: location
  tags: tags
}

module registry 'modules/registry.bicep' = {
  name: 'modelrisk-registry'
  scope: rg
  params: {
    location: location
    suffix: suffix
    environment: environment
    region: region
    tags: tags
    policyEffect: policyEffect
    logRetentionDays: logRetentionDays
    deployDriftAlert: deployDriftAlert
    alertEmail: alertEmail
    policyDefinitionIds: policies.outputs.ids
  }
}

output AZURE_RESOURCE_GROUP string = rg.name
output EVIDENCE_STORAGE_ACCOUNT string = registry.outputs.storageAccount
output WORKBOOK_ID string = registry.outputs.workbookId
