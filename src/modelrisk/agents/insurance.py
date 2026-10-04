"""Insurance: first-notice-of-loss claims triage for Bramblewood Mutual (fictional).

Small, well-documented claims are fast-tracked and paid up to a hard limit; the rest go to an
adjuster, and suspected fraud is proposed for a special-investigations referral (human approves).
"""

from __future__ import annotations

from modelrisk.agents.base import AgentSpec, rng
from modelrisk.agents.guardrails import ToolPolicy

FEATURES = ["claim_amount", "policy_age_months", "prior_claims", "doc_completeness", "photo_damage_match"]
RANGES = {
    "claim_amount": (0, 50000),
    "policy_age_months": (0, 240),
    "prior_claims": (0, 10),
    "doc_completeness": (0, 1),
    "photo_damage_match": (0, 1),
}
WEIGHTS = {"claim_amount": 6.0, "policy_age_months": -1.5, "prior_claims": 6.0, "doc_completeness": -3.5, "photo_damage_match": -2.0}
BIAS = 1.6
PROXIES = {"zip_risk_index": 2.5}
PAYOUT_LIMIT = 5000
NOTES = ["Rear bumper damage in a parking lot", "Water leak under the kitchen sink", "Hail damage to roof", "Cracked windshield"]


def generate(n: int, seed: int = 7, shift: float = 0.0) -> list[dict]:
    """Synthetic claims; ``shift`` = share of a fraud ring using aged shelf policies bought from
    brokers: policy ages beyond anything in training, small amounts, clean documents."""
    r = rng(seed)
    out = []
    for i in range(n):
        rural = r.random() < 0.35
        x = {
            "claim_amount": round(r.uniform(300, 4500) if r.random() < 0.7 else r.uniform(4500, 45000), 2),
            "policy_age_months": r.randint(1, 230),
            "prior_claims": r.choice([0, 0, 0, 1, 1, 2, 4]),
            "doc_completeness": round(r.uniform(0.5, 1.0), 2),
            "photo_damage_match": round(r.uniform(0.4, 1.0), 2),
            "zip_risk_index": round(min(1.0, r.uniform(0.4, 1.0) if rural else r.uniform(0.0, 0.5)), 2),
        }
        review = r.random() < SPEC.probability(x)
        if r.random() < shift:
            x.update(
                policy_age_months=r.randint(300, 480),
                claim_amount=round(r.uniform(1500, 4800), 2),
                doc_completeness=0.98,
                prior_claims=0,
                photo_damage_match=0.9,
            )
            review = True  # staged losses the model would fast-track
        out.append({"id": f"CLM-{i:05d}", "x": x, "group": "rural" if rural else "urban", "review": review, "untrusted": r.choice(NOTES)})
    return out


def decide(p: float, case: dict) -> str:
    if p >= 0.85:
        return "refer-siu"
    if p < 0.4 and case["x"]["claim_amount"] <= PAYOUT_LIMIT:
        return "fast-track"
    return "adjuster-review"


def action(decision: str, case: dict):
    return {
        "fast-track": ("approve_payout", {"amount": case["x"]["claim_amount"]}),
        "adjuster-review": ("assign_adjuster", {"claim": case["id"]}),
        "refer-siu": ("refer_siu", {"claim": case["id"]}),
    }[decision]


def evidence(case: dict, decision: str) -> dict[str, str]:
    x = case["x"]
    return {
        "policy-4.2": f"fast-track payouts are limited to {PAYOUT_LIMIT} for documented claims",
        "feat-docs": f"document completeness {x['doc_completeness']}",
        "feat-history": f"{x['prior_claims']} prior claims on this policy",
        "feat-photo": f"photo damage consistency {x['photo_damage_match']}",
    }


def policy(enforce: bool) -> ToolPolicy:
    return ToolPolicy(
        allowed={"get_policy", "approve_payout", "assign_adjuster", "refer_siu", "request_documents"},
        needs_approval={"refer_siu"},
        limits={"approve_payout": {"amount": PAYOUT_LIMIT}},
        enforce=enforce,
    )


SPEC = AgentSpec(
    id="bramblewood-claims-triage",
    company="Bramblewood Mutual",
    task="claims triage",
    features=FEATURES,
    ranges=RANGES,
    weights=WEIGHTS,
    bias=BIAS,
    proxy_weights=PROXIES,
    decide=decide,
    action=action,
    generate=generate,
    label=lambda c: c["review"],
    positive={"adjuster-review", "refer-siu"},
    evidence=evidence,
    policy=policy,
    favorable={"fast-track"},
    hitl_decisions={"adjuster-review", "refer-siu"},
)
