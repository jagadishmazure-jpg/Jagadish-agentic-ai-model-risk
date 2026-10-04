# ADR 0002: Executable links between the pillars

**Status:** Accepted

## Context

Four separate artifacts drift apart: risks the card implies are missing, data sheets disagree with code, scenarios test nothing material, results change nothing.

## Decision

Implement four links in `combine.py` (card to risks, data sheet to model, risks to scenarios, results to residual and backlog) and fail the gate (G5, G6) when one breaks.

## Consequences

Gaps surface on every change. The rules are explicit and simple, so they need extension for new model types.
