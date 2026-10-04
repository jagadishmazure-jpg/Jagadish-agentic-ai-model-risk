# Best practices this repository follows

## Model risk

1. **Every model has all four pillars**, validated by schema, before anything else is checked (G1, G2).
2. **Tier is computed** from the model card; only a documented floor can raise it.
3. **Residual risk is earned**: planned controls get no credit; scenario breaches remove credit.
4. **Every high or critical risk has an implemented control** (G3) and every material risk a scenario.
5. **Every scenario proves its control**: it must breach with the control off, or it becomes a backlog item.
6. **Validation is independent and re-performs** the card's numbers on a different seed.
7. **Approvals bind to a digest** of the pillars and expire; the audit log is hash-chained.
8. **Monitoring thresholds live on the card**, so they are reviewed and approved with it.

## Agentic AI

1. **The language model explains; a documented scoring model decides.**
2. **Authority lives in the tool layer**: allow-list, argument limits, approval-required tools.
3. **Untrusted text is screened** and never reaches the score.
4. **Out-of-range inputs go to people.**
5. **Every output is masked**; telemetry carries no text.
6. **Outage falls back to people**, measured at 100%.
7. **Budgets refuse before crossing the cap.**
8. **Claims must cite evidence.**

## Fairness

1. Protected attributes and known proxies are documented and excluded, and tests prove it.
2. Outcome parity (AIR) and individual consistency (matched pairs) are both tested.
3. Credit decisions and denials of care stay with people; the tools to make them do not exist.

## Engineering

1. Offline, deterministic, synthetic data; fictional companies only.
2. Docs carry real outputs and code excerpts, regenerated and drift-checked in CI.
3. Terraform and Bicep share policy JSON; smallest SKUs; deploy gated by `DEPLOY_ENABLED`, OIDC only.
4. No dates in docs, no unfinished placeholders, and a README in every folder.
5. Third-party frameworks are paraphrased and attributed, never copied.
