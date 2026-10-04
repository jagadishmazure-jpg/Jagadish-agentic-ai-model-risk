// Custom policy definitions, loaded from the same JSON files Terraform uses (infra/policies).
targetScope = 'subscription'

var defs = {
  'require-model-card-tags': loadJsonContent('../../policies/require-model-card-tags.json')
  'allowed-risk-tier': loadJsonContent('../../policies/allowed-risk-tier.json')
  'deny-public-ai-endpoints': loadJsonContent('../../policies/deny-public-ai-endpoints.json')
}

resource definitions 'Microsoft.Authorization/policyDefinitions@2023-04-01' = [for d in items(defs): {
  name: 'modelrisk-${d.key}'
  properties: {
    policyType: 'Custom'
    mode: d.value.mode
    displayName: d.value.displayName
    description: d.value.description
    metadata: d.value.metadata
    parameters: d.value.parameters
    policyRule: d.value.policyRule
  }
}]

output ids object = {
  'allowed-risk-tier': definitions[0].id
  'deny-public-ai-endpoints': definitions[1].id
  'require-model-card-tags': definitions[2].id
}
