# Interview guide

How to present this repository in 2, 10 and 30 minutes, with likely questions.

## Two minutes

"This is a model risk management system for agentic AI, built on four pillars credited to the Cloud
Security Alliance: model cards, data sheets, risk cards, plus scenario planning. Each pillar is a JSON
Schema and YAML per model, and the pillars are wired together in code: the card implies risks, the
data sheet is tested against the model, risks drive scenarios, and scenario results update residual
risk and generate the backlog. Five fictional enterprise agents (fraud, claims, mortgage underwriting,
prior authorization, pricing) run offline. A CI gate fails on a missing pillar, an uncontrolled high
risk or a scenario breach. Terraform and Bicep define Azure Policy, a workbook and an evidence store;
nothing is deployed."

## Ten minutes

1. `modelrisk inventory`: tiers versus EU AI Act classes (fraud tier 1 but minimal).
2. `modelrisk whatif --model juniper-prior-auth`: each control's value.
3. `modelrisk family --kind bias`: AIR 0.955 with proxy excluded, about 0.35 with it.
4. `modelrisk combine --model halcyon-fraud-triage`: the four links and the backlog.
5. `modelrisk lifecycle`: who still has to sign.
6. `modelrisk gate`: the merge decision.

<!-- output: risks --band critical -->
```text
model                               risk    category          L  I  inherent     controls  residual  owner
----------------------------------  ------  ----------------  -  -  -----------  --------  --------  ---------------
juniper-prior-auth                  HC-R1   legal-regulatory  4  5  20 critical  2         1.8 low   Privacy Office
cedarhollow-underwriting-assistant  MTG-R1  legal-regulatory  4  5  20 critical  2         1.6 low   Compliance
halcyon-fraud-triage                BNK-R1  operational       4  4  16 critical  2         3.36 low  Rhea Castellano
3 risks
```
<!-- /output -->

## Thirty minutes

Add the agent runtime (`docs/components/agent-runtime.md`), independent validation, the sign-off
digest and audit chain, the MCP server, the regulatory mapping and the infrastructure.

## Questions and answers

| Question | Answer |
|---|---|
| Why not just a model card? | A card alone does not prove anything. The links make gaps visible and blocking. |
| How do you score risk? | Likelihood × impact for inherent; residual applies implemented control effectiveness, compounded, capped at 0.9 each, adjusted by scenario results. |
| What does "inherent vs residual" buy you? | It separates the danger from the treatment, so you can see which controls carry the weight. |
| How do you know a control works? | Its scenario breaches when it is switched off. |
| Is the mock model a weakness? | It makes tests deterministic and worst case (it obeys every injection). Real models go through Foundry evaluations with repeated sampling. |
| How do you handle fair lending? | Proxy exclusion, AIR, matched pairs, human decisions, evidence-backed reasons, and a planned less discriminatory alternative search. |
| What blocks production? | Valid sign-offs on the current digest from the tier's roles, no breaches and a non-failing validation. Mortgage and healthcare are blocked now. |
| How does this map to SR 11-7? | Inventory, development documentation, independent validation, ongoing monitoring and governance. |
| EU AI Act? | Classes from declared uses; high-risk obligations mapped article by article. |
| Why both Terraform and Bicep? | Teams use either; both load the same policy JSON and a test proves it. |
| What is not done? | See the README's open gaps: attested external scenarios, mocks, regex screens, seeded sign-offs, nothing deployed. |

Pillar structure credited to the [CSA AI Technology and Risk working group](https://cloudsecurityalliance.org/research/working-groups/ai-technology-and-risk).
