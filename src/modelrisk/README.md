# modelrisk

The `modelrisk` package: pillars, governance, CLI and MCP server.

| File | What it does |
|---|---|
| `__init__.py` | Paths (ROOT, REGISTRY, SCHEMAS, REGULATORY, EVIDENCE) |
| `agents/` | Domain agents and runtime |
| `scenarios/` | Scenario engine |
| `cli.py` | The `modelrisk` command |
| `combine.py` | The four pillar links, residual update, backlog |
| `evaluation.py` | Metrics on synthetic data |
| `gate.py` | CI gate G1-G8 |
| `iac.py` | Summaries of the IaC files |
| `lifecycle.py` | Stages and required roles |
| `mcp_server.py` | Read-only MCP server |
| `monitoring.py` | PSI and performance monitoring |
| `registry.py` | Loads pillars per model |
| `report.py` | Text tables and heatmap |
| `schema.py` | JSON Schema validation |
| `scoring.py` | Likelihood × impact, residual, appetite |
| `signoff.py` | HITL sign-off and audit chain |
| `telemetry.py` | Governance events |
| `tiering.py` | Materiality tier and EU AI Act class |
| `validation.py` | Independent validation |
