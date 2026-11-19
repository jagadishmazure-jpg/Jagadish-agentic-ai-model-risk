# ADR 0007: Offline sandbox controls for agent sessions

**Status:** Accepted

## Context

A sandbox that contains agent code does not decide which network resources, saved model work or third-party MCP servers a session may use. Hosted controls for the first two are described in a preview announcement. This repository cannot call them, and its tests have to pass with no network and no credentials.

## Decision

Three offline engines stand in. A deny-by-default network policy records every reach on a hash-chained log, and an explicit deny beats a broader allow. A context cache saves completed steps so a new worker does not repeat those model calls. An allowlist admits an MCP server only at an exact reviewed pin. An examiner pack replays all three and maps the results onto `regulatory/mapping.yaml`. Preview product behaviour is marked [verify] and is not executed.

## Consequences

CI can show a refused reach, a resume with no duplicate model call, and a rejected MCP declaration without a live cloud. The engines are not a packet filter, a hosted cache or a vulnerability scanner. The five domain graphs do not call them on every node yet; the demos and the pack are the evidence.
