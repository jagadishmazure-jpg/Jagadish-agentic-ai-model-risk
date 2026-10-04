# ADR 0003: Deterministic mock model and synthetic data

**Status:** Accepted

## Context

Scenarios must be repeatable in CI without keys, cost or network, and must be worst case.

## Decision

A `MockLLM` with knobs (obey injections, hallucinate, echo input, fail, retry storm) and seeded synthetic generators per domain with known weights.

## Consequences

Tests are fast and deterministic; scenario metrics are clean. Real models need Foundry evaluations with sampling, documented as the path to production.
