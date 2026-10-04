# Pillar 3: risk cards

Risk cards list the ways a model can cause harm, how likely and how severe each one is, which
controls reduce it, who owns it and which scenarios test it. Scores are likelihood × impact for
inherent risk; residual risk applies the credited effectiveness of implemented controls. The risk
card as a pillar, and the idea of grouping risks into families, is credited to the Cloud Security
Alliance AI Technology and Risk working group
([framework page](https://cloudsecurityalliance.org/research/working-groups/ai-technology-and-risk));
the nine-category enum, harm codes H1 to H6 and the scoring code are this repository's own.

Sections: [1. Purpose](#1-purpose) · [2. Architecture](#2-architecture) · [3. How it works](#3-how-it-works) · [4. Key files](#4-key-files) · [5. Code excerpts](#5-code-excerpts) · [6. Configuration](#6-configuration) · [7. Commands](#7-commands) · [8. Real output](#8-real-output) · [9. Tests and gates](#9-tests-and-gates) · [10. Guardrails](#10-guardrails) · [11. Security and governance](#11-security-and-governance) · [12. Observability](#12-observability) · [13. Failure modes](#13-failure-modes) · [14. Mapping to Azure services](#14-mapping-to-azure-services) · [15. Limitations](#15-limitations) · [16. Interview talking points](#16-interview-talking-points)

## 1. Purpose

* One register of risks across ten models, with named owners and controls that have owners too.
* Scores that move: inherent is fixed by likelihood and impact, residual changes when scenarios
  show a control works less well than claimed.
* Every material risk (inherent 10 or more) must be exercised by at least one scenario.

## 2. Architecture

```mermaid
flowchart TB
  R[risk: likelihood 1-5 x impact 1-5] --> INH[inherent 1-25<br/>low / medium / high / critical]
  C1[control A: effectiveness e1] --> CE[combined = 1 - (1-e1)(1-e2)...<br/>implemented controls only]
  C2[control B: effectiveness e2] --> CE
  INH --> RES[residual = inherent x (1 - combined)]
  CE --> RES
  SC[scenario results] -->|pass 1.0 / warn 0.5 / breach 0| CE
  RES --> AP{within tier appetite?}
  AP -->|no| BL[P1 backlog + gate G6 fails]
```

## 3. How it works

1. Each risk has an id, title, category (safety-ethics, security, societal, environmental,
   operational, legal-regulatory, financial, supply-chain, reputational), a harm code
   (H1 discrimination, H2 information hazard, H3 misinformation, H4 malicious use, H5 human
   interaction, H6 automation and environment), a description, an impact description, likelihood,
   impact, owner, controls, scenarios and its source (model card, data sheet, scenario...).
2. Controls carry type (preventive, detective, corrective), effectiveness (0 to 0.9), owner,
   status (implemented or planned), evidence and an optional `runtime_control`: the flag in the
   agent runtime that implements it.
3. `scoring.score_risk` computes inherent, combined effectiveness and residual; planned controls
   earn nothing.
4. `combine.update_residuals` re-scores each risk with control credit adjusted by scenario results.
5. Residual band is compared with the tier appetite: tier 1 low, tiers 2 and 3 medium.

## 4. Key files

| File | Role |
|---|---|
| `schemas/risk-card.schema.json` | Risk and control structure, category and harm enums |
| `registry/<model-id>/risk-cards.yaml` | 48 risks across ten models |
| `src/modelrisk/scoring.py` | Bands, combined effectiveness, residual, appetite, heatmap |
| `src/modelrisk/combine.py` | `update_residuals` and `backlog` |
| `src/modelrisk/mcp_server.py` | `query_risks` and `risk_heatmap` tools |

## 5. Code excerpts

<!-- code: src/modelrisk/scoring.py::combined_effectiveness -->
```python
def combined_effectiveness(controls: list[dict[str, Any]], overrides: dict[str, float] | None = None) -> float:
    overrides = overrides or {}
    remaining = 1.0
    for c in controls:
        if c.get("status") != "implemented":
            continue
        remaining *= 1 - overrides.get(c["id"], c["effectiveness"])
    return round(1 - remaining, 4)
```
<!-- /code -->

<!-- code: src/modelrisk/scoring.py::score_risk -->
```python
def score_risk(risk: dict[str, Any], overrides: dict[str, float] | None = None) -> dict[str, Any]:
    inherent = risk["likelihood"] * risk["impact"]
    eff = combined_effectiveness(risk["controls"], overrides)
    residual = round(inherent * (1 - eff), 2)
    return {
        "id": risk["id"],
        "title": risk["title"],
        "category": risk["category"],
        "owner": risk["owner"],
        "likelihood": risk["likelihood"],
        "impact": risk["impact"],
        "inherent": inherent,
        "inherent_band": band(inherent),
        "control_effectiveness": eff,
        "residual": residual,
        "residual_band": band(residual),
        "implemented_controls": sum(c["status"] == "implemented" for c in risk["controls"]),
    }
```
<!-- /code -->

<!-- code: src/modelrisk/scoring.py::APPETITE -->
```python
APPETITE = {1: "low", 2: "medium", 3: "medium"}
```
<!-- /code -->

## 6. Configuration

| Setting | Value | Where |
|---|---|---|
| Bands | low 1-4, medium 5-9, high 10-15, critical 16-25 | `scoring.BANDS` |
| Effectiveness cap | 0.9 | schema |
| Appetite | tier 1 low, tier 2 medium, tier 3 medium | `scoring.APPETITE` |
| Scenario credit | pass 1.0, warn 0.5, breach 0 | `combine.CREDIT` |

## 7. Commands

```bash
modelrisk risks --band high
modelrisk heatmap
modelrisk risks --model juniper-prior-auth
```

## 8. Real output

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

<!-- output: heatmap -->
```text
inherent risk heatmap: all models (48 risks)
impact \ likelihood   1  2  3  4  5
        5             .  3  2  2  .
        4             .  3  18  1  .
        3             .  5  10  1  .
        2             .  1  2  .  .
        1             .  .  .  .  .
```
<!-- /output -->

<!-- output: risks --model juniper-prior-auth -->
```text
model               risk   category          L  I  inherent     controls  residual  owner
------------------  -----  ----------------  -  -  -----------  --------  --------  -----------------------
juniper-prior-auth  HC-R1  legal-regulatory  4  5  20 critical  2         1.8 low   Privacy Office
juniper-prior-auth  HC-R4  safety-ethics     3  5  15 high      1         1.5 low   Dr. Lena Moravec
juniper-prior-auth  HC-R2  safety-ethics     3  4  12 high      1         2.4 low   Dr. Lena Moravec
juniper-prior-auth  HC-R3  security          3  4  12 high      1         3.6 low   Security Operations
juniper-prior-auth  HC-R6  societal          3  4  12 high      1         3.0 low   Compliance
juniper-prior-auth  HC-R5  operational       3  3  9 medium     1         2.7 low   AI Platform Engineering
juniper-prior-auth  HC-R8  operational       3  3  9 medium     1         3.15 low  Model Risk Management
juniper-prior-auth  HC-R7  financial         2  3  6 medium     1         1.2 low   AI Platform Engineering
8 risks
```
<!-- /output -->

## 9. Tests and gates

* `tests/test_scoring_tiering.py`: bands, compounding, planned controls, overrides, appetite, heatmap.
* `tests/test_gate.py::test_high_risk_without_implemented_control_fails` (gate G3) and
  `test_residual_over_appetite_fails` (gate G6).
* `tests/test_combine.py`: breach removes credit, warn halves it, backlog items appear.

## 10. Guardrails

* No control can claim more than 0.9, so residual never reaches zero on paper.
* Planned controls are listed (and become backlog items) but do not lower residual risk.
* Every high and critical risk needs at least one implemented control (G3).

## 11. Security and governance

Each risk and each control has an owner. Owners are functions or named fictional people, and
they appear in the MCP `query_risks` results so an agent or a person can ask "what do I own?".

## 12. Observability

`modelrisk.residual` events carry residual and `within_appetite` per risk; the workbook lists any
risk above appetite.

## 13. Failure modes

| Failure | Caught by |
|---|---|
| High risk with only planned controls | G3 |
| Optimistic effectiveness | scenarios; a breach drops the credit to zero and fails G6 if appetite is exceeded |
| Risk with no owner | schema (owner required) |
| Material risk never tested | `scenario_links`, G5 |

## 14. Mapping to Azure services

* **Microsoft Purview**: risk owners and categories can be mirrored into Purview's data map as
  business metadata for the data assets each risk touches.
* **Foundry evaluations**: safety evaluators supply evidence for H2, H3 and H4 risks.
* **Azure Policy**: the `risk-tier` tag carries the inventory tier onto resources.
* **Application Insights**: residual-risk events and the workbook view.

## 15. Limitations

* Likelihood and impact are expert judgements on a five-point scale.
* Combined effectiveness assumes controls fail independently.

## 16. Interview talking points

* "Residual risk is earned: planned controls get no credit and scenario breaches remove it."
* "Each control can name the runtime flag that implements it, which is how the what-if knows
  what to switch off."
* "48 risks, 3 critical, all inside appetite after testing, with the backlog showing what is still planned.
