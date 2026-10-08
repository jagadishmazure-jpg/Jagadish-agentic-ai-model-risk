# Changelog

All notable changes to this project are documented here.

## Unreleased

### Added

- Supply-chain hardening: every GitHub Action pinned to a commit SHA with a version comment, top-level `permissions` on every workflow, a gitleaks job in CI, a CodeQL workflow, `.github/dependabot.yml` and a guard test (`test_workflows_are_hardened`).
- GitHub settings: Dependabot alerts and security updates, private vulnerability reporting and a `main` ruleset (no force-push or deletion; CI required on pull requests).
- Four pillars as JSON Schema and YAML: model cards, data sheets, risk cards, scenarios.
- Executable pillar links: card to required risks, data sheet understanding checks, risk-to-scenario
  links, scenario results to residual risk and a generated backlog.
- Five fictional domain agents on a LangGraph-style runtime with a mock model: fraud triage, claims,
  mortgage underwriting (fair-lending tests), prior authorization (PHI masking), pricing and demand.
- Scenario engine for eight families, each run with controls on and off.
- Inventory and tiering, EU AI Act classes, lifecycle gates, independent validation, monitoring.
- HITL sign-off with digest binding and a hash-chained audit log; read-only MCP server.
- Portfolio cards governing components of five other repositories.
- Regulatory mapping (CSA pillars, NIST AI RMF, EU AI Act, SR 11-7, ISO/IEC 42001, HIPAA, fair lending).
- Terraform and Bicep evidence plane with Azure Policy, workbook and storage; gated GitHub Actions.
- Full documentation with regenerated outputs and code excerpts.
