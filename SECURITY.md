# Security policy

## Scope

This repository contains offline code, synthetic data and infrastructure templates for fictional
companies. It holds no credentials, subscription or tenant identifiers, model keys, or real customer,
patient or applicant data, and its tests enforce that.

## Reporting a vulnerability

Please open a private security advisory on GitHub (Security tab, "Report a vulnerability") rather
than a public issue. Include the file, the problem and how to reproduce it.

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

## Supported versions

Only the `main` branch is maintained.
