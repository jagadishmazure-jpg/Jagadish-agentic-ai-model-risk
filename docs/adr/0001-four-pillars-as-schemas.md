# ADR 0001: Four pillars as JSON Schema and YAML per model

**Status:** Accepted

## Context

Model governance documents are usually prose, which cannot be checked. The CSA framework's four tools (model cards, data sheets, risk cards, scenario planning) need to be machine-checkable to gate CI.

## Decision

Each pillar is a JSON Schema (draft 2020-12, no unknown fields) and one YAML file per model under `registry/<model-id>/`. Code reads the YAML; nothing is duplicated in prose.

## Consequences

Pillars can be validated, diffed, digested for sign-off and served over MCP. Authors write YAML, not documents; the docs explain the format.
