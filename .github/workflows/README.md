# workflows

Workflows. Deploy and teardown are gated by `DEPLOY_ENABLED` (unset).

| File | What it does |
|---|---|
| `ci.yml` | Lint, tests, gate, doc drift, bicep build |
| `infra.yml` | Terraform checks and plan if OIDC vars |
| `deploy.yml` | Gated dev to prod, OIDC, Terraform or Bicep |
| `teardown.yml` | Gated, confirmed teardown |
