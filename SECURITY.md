# Security policy

## Scope

This repository contains offline code, synthetic data and infrastructure templates for fictional
companies. It holds no credentials, subscription or tenant identifiers, model keys, or real customer,
patient or applicant data, and its tests enforce that.

## Reporting a vulnerability

Please do not open a public issue with the details.

1. Open a private security advisory on GitHub (Security tab, "Report a vulnerability"). Include the
   file, the problem and how to reproduce it.
2. If that button is not shown, open an issue titled `Security contact request` with no technical
   details, and I will reply with a private channel.

I aim to acknowledge a report within 5 working days. This is a personal portfolio maintained by one
person, so there is no formal SLA or bug bounty.

## Design choices that matter for security

- **No secrets anywhere.** GitHub Actions log in to Azure with OIDC federated credentials; there is no
  client secret. Storage has shared keys disabled and Application Insights has local auth disabled.
- **Agents cannot exceed their authority.** Tools are allow-listed with argument limits; card blocks
  and SIU referrals need a person; the mortgage assistant has no decision tool and the prior
  authorization agent has no deny tool.
- **Untrusted text is screened** and never reaches the scoring model; every output is masked for PII
  (and PHI in healthcare); telemetry carries ids and numbers, never text.
- **Human sign-off is tamper-evident.** Approvals are bound to a digest of the pillars, refuse self
  sign-off, expire, and are written to a hash-chained audit log that the CI gate verifies.
- **The MCP server is read-only** (every tool annotated read-only and non-destructive).
- **Deploy gated off** until `DEPLOY_ENABLED` is set; prod needs environment reviewers.
- **Scanned IaC.** checkov and tflint run on Terraform in CI; each skipped check is justified.
- **Supply chain:** every third-party GitHub Action is pinned to a full commit SHA with its version in a comment, and every workflow starts from read-only `permissions`. Dependabot proposes weekly, grouped updates ([`.github/dependabot.yml`](.github/dependabot.yml)); CodeQL scans the Python code and the workflow files ([`codeql.yml`](.github/workflows/codeql.yml)); gitleaks scans the full git history in CI. A test (`test_workflows_are_hardened`) fails if an action is left unpinned or a workflow loses its `permissions` block.
- **SBOM:** the `sbom` job in [`ci.yml`](.github/workflows/ci.yml) builds an SPDX JSON software bill of materials from the lockfiles and manifests on every run and keeps it as the `sbom.spdx.json` build artifact. The repository ships no container image, so there is no image scan or provenance step.
- **GitHub settings:** secret scanning with push protection, Dependabot alerts and security updates, private vulnerability reporting, and a ruleset on `main` that blocks force-pushes and branch deletion and requires the CI checks before a pull request can merge. The maintainer (repository admin) can still push directly to `main`, so for direct pushes the checks run after the push rather than before it.

## Supported versions

Only the `main` branch is maintained.
