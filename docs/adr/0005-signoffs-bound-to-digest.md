# ADR 0005: Sign-offs bound to a pillar digest with a hash-chained log

**Status:** Accepted

## Context

Approvals must stay attached to what was approved, and tampering must be detectable.

## Decision

A sign-off records the SHA-256 digest of the parsed pillars; entries go to an append-only JSON lines log where each entry hashes the previous one. Self sign-off, owner-as-validator and empty rationales are refused; approvals expire after 365 days.

## Consequences

Any pillar edit invalidates approvals until people re-sign; the demo seeds fictional sign-offs with a script.
