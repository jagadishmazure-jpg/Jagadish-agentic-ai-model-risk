# workflows

Workflows. Deploy and teardown are gated by `DEPLOY_ENABLED` (unset).

| File | What it does |
|---|---|
| `ci.yml` | Lint, tests, gate, doc drift, bicep build; a `secrets` job runs gitleaks over the full git history. |
| `codeql.yml` | CodeQL for Python and for the workflow files (`actions`), on push, pull request and weekly. Results appear under Security -> Code scanning and do not fail the build. |
| `infra.yml` | Terraform checks and plan if OIDC vars |
| `deploy.yml` | Gated dev to prod, OIDC, Terraform or Bicep |
| `teardown.yml` | Gated, confirmed teardown |

**Supply chain.** Every third-party action is pinned to a full commit SHA with the version in a comment, and every workflow starts from `permissions: contents: read`; jobs that need more (OIDC sign-in, CodeQL uploads) ask for it themselves. Dependabot ([`../dependabot.yml`](../dependabot.yml)) proposes weekly grouped updates that move the SHA and the comment together, and `tests/test_iac.py::test_workflows_are_hardened` fails CI if an action is left unpinned.

**SBOM.** The `sbom` job in `ci.yml` writes an SPDX JSON bill of materials for the source tree on every run (artifact `sbom.spdx.json`).
