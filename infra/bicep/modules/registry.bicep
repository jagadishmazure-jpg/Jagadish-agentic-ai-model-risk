// Resource-group scope: policy assignments, Log Analytics, App Insights, workbook, evidence
// storage with blob diagnostics, and the opt-in drift alert.
param location string
param suffix string
@allowed(['dev', 'prod'])
param environment string
@allowed(['eus2', 'wus2', 'weu'])
param region string
param tags object
@allowed(['Audit', 'Deny', 'Disabled'])
param policyEffect string
param logRetentionDays int
param deployDriftAlert bool
param alertEmail string
param policyDefinitionIds object

resource assignments 'Microsoft.Authorization/policyAssignments@2024-04-01' = [for p in items(policyDefinitionIds): {
  name: 'modelrisk-${p.key}'
  properties: {
    policyDefinitionId: p.value
    parameters: {
      effect: { value: policyEffect }
    }
  }
}]

resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-modelrisk-${suffix}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: logRetentionDays
    workspaceCapping: { dailyQuotaGb: json('0.5') }
  }
}

resource appi 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-modelrisk-${suffix}'
  location: location
  kind: 'other'
  tags: tags
  properties: {
    Application_Type: 'other'
    WorkspaceResourceId: law.id
    DisableLocalAuth: true
  }
}

resource workbook 'Microsoft.Insights/workbooks@2023-06-01' = {
  name: guid(resourceGroup().id, 'modelrisk-workbook', suffix)
  location: location
  kind: 'shared'
  tags: tags
  properties: {
    displayName: 'Model risk register (${environment})'
    category: 'workbook'
    sourceId: toLower(appi.id)
    serializedData: string(loadJsonContent('../../workbook/model-risk-workbook.json'))
  }
}

resource evidence 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'stmodelrisk${environment}${region}001'
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  tags: tags
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowSharedKeyAccess: false
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

resource blob 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: evidence
  name: 'default'
  properties: {
    isVersioningEnabled: true
    deleteRetentionPolicy: { enabled: true, days: 30 }
    containerDeleteRetentionPolicy: { enabled: true, days: 30 }
  }
}

resource containers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = [for c in ['evidence', 'model-cards', 'audit']: {
  parent: blob
  name: c
  properties: { publicAccess: 'None' }
}]

resource blobDiag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'diag-evidence-blob'
  scope: blob
  properties: {
    workspaceId: law.id
    logs: [
      { category: 'StorageRead', enabled: true }
      { category: 'StorageWrite', enabled: true }
      { category: 'StorageDelete', enabled: true }
    ]
  }
}

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = if (deployDriftAlert) {
  name: 'ag-modelrisk-${suffix}'
  location: 'global'
  tags: tags
  properties: {
    groupShortName: 'modelrisk'
    enabled: true
    emailReceivers: [
      { name: 'model-risk', emailAddress: alertEmail, useCommonAlertSchema: true }
    ]
  }
}

resource driftAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = if (deployDriftAlert) {
  name: 'alert-drift-${suffix}'
  location: location
  tags: tags
  properties: {
    severity: 2
    enabled: true
    evaluationFrequency: 'PT1H'
    windowSize: 'PT1H'
    scopes: [appi.id]
    description: 'A model\'s score PSI reached the alert threshold from its model card.'
    criteria: {
      allOf: [
        {
          query: 'customEvents | where name == \'modelrisk.drift\' | where todouble(customDimensions.psi_score) >= 0.25'
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: { numberOfEvaluationPeriods: 1, minFailingPeriodsToAlert: 1 }
        }
      ]
    }
    actions: { actionGroups: deployDriftAlert ? [actionGroup.id] : [] }
  }
}

output storageAccount string = evidence.name
output workbookId string = workbook.id
