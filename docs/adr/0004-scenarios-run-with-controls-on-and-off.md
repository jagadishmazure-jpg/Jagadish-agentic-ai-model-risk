# ADR 0004: Every scenario runs with controls on and off

**Status:** Accepted

## Context

A passing scenario does not show that a control is needed; it may pass for unrelated reasons.

## Decision

Each control on a risk card may name a `runtime_control`. The engine runs each scenario with defaults (the gate) and with the linked risks' runtime controls off (the what-if). A what-if that still passes creates a P3 backlog item.

## Consequences

Control value is measured. One banking scenario (BNK-S7) is honest about not exercising its control.
