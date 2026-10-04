# registry

One folder per model with the four pillars and approvals, plus the inventory and audit log.

| File | What it does |
|---|---|
| `halcyon-fraud-triage/` | Halcyon Trust Bank fraud triage agent (banking, tier 1, EU minimal) |
| `bramblewood-claims-triage/` | Bramblewood Mutual claims triage agent (insurance, tier 1) |
| `cedarhollow-underwriting-assistant/` | Cedar Hollow Lending underwriting assistant (mortgage, tier 1, EU high-risk) |
| `juniper-prior-auth/` | Juniper Health Plan prior authorization agent (healthcare, tier 1, EU high-risk, not a medical device) |
| `marigold-pricing-demand/` | Marigold Market pricing and demand agent (retail, tier 2) |
| `pfa-mortgage-flow/` | Governs the mortgage flow in Jagadish-azure-agent-platform |
| `pfs-safety-layer/` | Governs the safety layer in Jagadish-azure-ai-integration-platform |
| `pal-agent-labs/` | Governs the labs in Jagadish-azure-agent-labs |
| `pfb-fabric-data-agent/` | Governs the Fabric data agent in Jagadish-fabric-enterprise-bi |
| `pff-finops-agent/` | Governs the FinOps agent in Jagadish-azure-finops |
| `inventory.yaml` | The model inventory |
| `audit-log.jsonl` | Hash-chained sign-off log |
