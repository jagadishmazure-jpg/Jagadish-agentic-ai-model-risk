# Changelog

All notable changes to this project are documented here.

## Unreleased

### Added

- Session network policy: deny-by-default reach decisions for a sandboxed agent, explicit deny over a broader allow, hash-chained audit log. Offline stand-in for a policy next to the sandbox. Preview product behaviour is marked [verify].
- Context cache: saved work so a new worker resumes without repeating completed model calls. Tests require a duplicate count of zero.
- MCP supply check: allowlist and exact pins, including `mcp-server-git` 2026.11.18 and `@modelcontextprotocol/server-filesystem` 2.4.0. Defensive only; no vulnerability detail.
- Synthetic examiner pack (`modelrisk examiner`) generated from those three controls and mapped onto `regulatory/mapping.yaml`.
- Threat model (`docs/security/threat-model.md`): STRIDE, OWASP Top 10 for LLM Applications and MITRE ATLAS mapped to this repository's components, each row with its control, test evidence and built / planned status.
- SBOM job in CI: an SPDX JSON software bill of materials of the source tree on every run (artifact `sbom.spdx.json`).
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
