# ADR 0006: Terraform and Bicep, deploy gated off

**Status:** Accepted

## Context

The repository should show a real Azure evidence plane without deploying or holding credentials.

## Decision

Two equivalent stacks loading the same policy and workbook JSON; deploy and teardown workflows run only when `DEPLOY_ENABLED` is `true`, use OIDC and require environment approval for prod.

## Consequences

Reviewable infrastructure with zero spend. Plans run only when OIDC variables exist.
