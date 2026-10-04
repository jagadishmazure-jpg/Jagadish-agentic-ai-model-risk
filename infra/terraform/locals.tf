locals {
  short  = "modelrisk"
  region = { eastus2 = "eus2", westus2 = "wus2", westeurope = "weu" }[var.location]
  suffix = "${var.environment}-${local.region}-001"
  tags = merge({
    "env"         = var.environment
    "owner"       = "model-risk-management"
    "app"         = "agentic-ai-model-risk"
    "cost-center" = "CC-7100"
    "managed-by"  = "terraform"
  }, var.tags)
  policies = {
    "require-model-card-tags"  = jsondecode(file("${path.module}/../policies/require-model-card-tags.json"))
    "allowed-risk-tier"        = jsondecode(file("${path.module}/../policies/allowed-risk-tier.json"))
    "deny-public-ai-endpoints" = jsondecode(file("${path.module}/../policies/deny-public-ai-endpoints.json"))
  }
  policy_parameters   = { for k, _ in local.policies : k => { effect = { value = var.policy_effect } } }
  evidence_containers = ["evidence", "model-cards", "audit"]
}
