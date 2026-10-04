# Architecture

```mermaid
flowchart TB
  subgraph Registry[registry: one folder per model]
    MC[model-card.yaml] --- DS[data-sheet.yaml] --- RC[risk-cards.yaml] --- SC[scenarios.yaml] --- AP[approvals.yaml]
  end
  SCH[schemas/*.json] --> V[schema validation]
  Registry --> V
  Registry --> TIER[tiering + inventory]
  Registry --> COMB[combine: 4 pillar links]
  AG[agents: 5 domain agents<br/>graph runtime + MockLLM] --> ENG[scenario engine]
  SC --> ENG --> COMB
  COMB --> RES[residual + backlog]
  AG --> VAL[independent validation] & MON[monitoring]
  AP --> LC[lifecycle gates] --> GATE
  RES --> GATE[CI gate G1-G8]
  VAL --> GATE
  LOG[audit-log.jsonl] --> GATE
  GATE --> TEL[telemetry events] --> AZ[(Azure: App Insights, workbook,<br/>evidence storage, Azure Policy)]
  Registry --> MCP[MCP server, read-only]
  REG[regulatory/mapping.yaml] --> MCP
```

## Layers

| Layer | Code | Docs |
|---|---|---|
| Pillars (artifacts + schemas) | `schemas/`, `registry/` | `docs/pillars/` |
| Agents | `src/modelrisk/agents/` | `docs/domains/`, `docs/components/agent-runtime.md` |
| Scenario engine | `src/modelrisk/scenarios/` | `docs/scenarios/` |
| Governance | `tiering.py`, `combine.py`, `lifecycle.py`, `validation.py`, `monitoring.py`, `signoff.py`, `gate.py` | `docs/components/` |
| Interfaces | `cli.py`, `mcp_server.py`, `telemetry.py` | `docs/components/` |
| Infrastructure | `infra/` | `docs/infra/` |

## Azure mapping

| Concern | Here | Azure |
|---|---|---|
| Model hosting | MockLLM | Microsoft Foundry deployments |
| Evaluations | scenario engine | Foundry evaluations and red teaming agent |
| Injection screen | regex | Azure AI Content Safety Prompt Shields |
| PII/PHI masking | regex | Azure AI Language PII detection |
| Data governance | data sheets | Microsoft Purview |
| Resource guardrails | tests on tags | Azure Policy (`infra/policies`) |
| Telemetry | JSON lines | Application Insights + Log Analytics workbook |
| Evidence | `evidence/` | Storage account, versioned, keyless |

Pillar structure credited to the [CSA AI Technology and Risk working group](https://cloudsecurityalliance.org/research/working-groups/ai-technology-and-risk).
