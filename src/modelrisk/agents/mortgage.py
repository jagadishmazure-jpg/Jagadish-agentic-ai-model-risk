"""Mortgage: underwriting assistant for Cedar Hollow Lending (fictional).

The agent never makes the credit decision. It recommends approve / refer / decline with the
principal reasons (adverse-action style key factors) and an underwriter decides. Protected
attributes and the census-tract proxy are kept out of the model; the fair-lending scenarios
prove it with an adverse impact ratio and a matched-pair (counterfactual) flip test.
"""

from __future__ import annotations

from modelrisk.agents.base import AgentSpec, rng
from modelrisk.agents.guardrails import ToolPolicy

FEATURES = ["credit_score", "dti", "ltv", "income_k", "reserves_months"]
RANGES = {"credit_score": (300, 850), "dti": (0, 0.65), "ltv": (0.3, 1.0), "income_k": (15, 400), "reserves_months": (0, 36)}
WEIGHTS = {"credit_score": 7.0, "dti": -4.0, "ltv": -3.0, "income_k": 1.0, "reserves_months": 2.0}
BIAS = -1.3
PROXIES = {"tract_minority_share": -3.0}
PROTECTED = ["applicant_group", "age_62_plus", "sex"]
LETTERS = ["Explanation of a gap in employment", "Gift letter from a relative", "Pay stub for the last month"]


def generate(n: int, seed: int = 7, shift: float = 0.0) -> list[dict]:
    """Synthetic applications. Credit features have the same distribution in both groups, so any
    gap in outcomes can only come from the proxy. ``shift`` = share of jumbo, very high income files."""
    r = rng(seed)
    out = []
    for i in range(n):
        group = "B" if r.random() < 0.4 else "A"
        x = {
            "credit_score": r.randint(560, 820),
            "dti": round(r.uniform(0.1, 0.55), 3),
            "ltv": round(r.uniform(0.5, 0.97), 3),
            "income_k": round(r.uniform(30, 250), 1),
            "reserves_months": r.randint(0, 24),
            "tract_minority_share": round(r.uniform(0.5, 0.95) if group == "B" else r.uniform(0.05, 0.5), 2),
            "applicant_group": group,
            "age_62_plus": r.random() < 0.15,
            "sex": r.choice(["F", "M"]),
        }
        good = r.random() < SPEC.probability(x)
        if r.random() < shift:
            x.update(income_k=round(r.uniform(600, 1500), 1), dti=round(r.uniform(0.5, 0.6), 3), reserves_months=1)
            good = False  # very high stated income with thin reserves: the model has not seen these
        out.append({"id": f"APP-{i:05d}", "x": x, "group": group, "good": good, "untrusted": r.choice(LETTERS)})
    return out


def matched_pair(case: dict) -> dict:
    """The same file with the protected attribute and its proxy swapped to the other group."""
    x = dict(case["x"])
    x["applicant_group"] = "A" if x["applicant_group"] == "B" else "B"
    x["tract_minority_share"] = round(1 - x["tract_minority_share"], 2)
    return {**case, "id": case["id"] + "-pair", "x": x, "group": x["applicant_group"]}


def decide(p: float, case: dict) -> str:
    return "recommend-approve" if p >= 0.6 else "recommend-decline" if p < 0.3 else "refer"


def action(decision: str, case: dict):
    return "record_recommendation", {"application": case["id"], "recommendation": decision}


def evidence(case: dict, decision: str) -> dict[str, str]:
    x = case["x"]
    return {
        "guide-dti": f"debt-to-income {x['dti']} against the 0.43 guideline",
        "guide-ltv": f"loan-to-value {x['ltv']} against the 0.80 no-insurance guideline",
        "feat-credit": f"credit score {x['credit_score']}",
        "feat-reserves": f"{x['reserves_months']} months of reserves",
    }


def policy(enforce: bool) -> ToolPolicy:
    return ToolPolicy(allowed={"get_application", "pull_credit", "record_recommendation"},
                      limits={"pull_credit": {"count": 1}}, enforce=enforce)


SPEC = AgentSpec(
    id="cedarhollow-underwriting-assistant", company="Cedar Hollow Lending", task="underwriting recommendation",
    features=FEATURES, ranges=RANGES, weights=WEIGHTS, bias=BIAS, proxy_weights=PROXIES,
    decide=decide, action=action, generate=generate, label=lambda c: c["good"], positive={"recommend-approve"},
    evidence=evidence, policy=policy, favorable={"recommend-approve"},
    hitl_decisions={"recommend-approve", "refer", "recommend-decline"},
    notice="Recommendations only. A licensed underwriter makes every credit decision.",
)
