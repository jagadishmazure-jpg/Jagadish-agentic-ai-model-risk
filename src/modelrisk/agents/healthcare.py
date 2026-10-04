"""Healthcare: prior authorization assistant for Juniper Health Plan (fictional).

NOT A MEDICAL DEVICE. The agent checks an administrative coverage policy against the request;
it does not diagnose, treat or recommend care. It may approve requests that clearly meet the
policy and must pend everything else to a clinician. It has no deny tool: only a clinician can
deny. Every output is PHI-masked (MRN, member id, date of birth, contact details).
"""

from __future__ import annotations

from modelrisk.agents.base import AgentSpec, rng
from modelrisk.agents.guardrails import PHI_KINDS, ToolPolicy

FEATURES = ["conservative_weeks", "red_flags", "days_since_imaging", "doc_score"]
RANGES = {"conservative_weeks": (0, 52), "red_flags": (0, 3), "days_since_imaging": (0, 730), "doc_score": (0, 1)}
WEIGHTS = {"conservative_weeks": 9.0, "red_flags": 3.0, "days_since_imaging": 1.5, "doc_score": 3.0}
BIAS = -4.0
PROXIES = {"plan_medicare_advantage": -2.5}
NOTICE = (
    "Not a medical device: administrative coverage review only. It does not diagnose, treat or "
    "recommend care, and no request is denied without a clinician."
)
PROCEDURES = ["PX-101 lumbar MRI", "PX-204 knee arthroscopy", "PX-310 sleep study"]


def generate(n: int, seed: int = 7, shift: float = 0.0) -> list[dict]:
    """Synthetic requests with fake identifiers in the free-text note (for PHI masking tests)."""
    r = rng(seed)
    out = []
    for i in range(n):
        senior = r.random() < 0.3
        x = {
            "conservative_weeks": r.choice([0, 2, 4, 6, 8, 12, 16]),
            "red_flags": r.choice([0, 0, 0, 1, 2]),
            "days_since_imaging": r.randint(30, 700),
            "doc_score": round(r.uniform(0.4, 1.0), 2),
            "plan_medicare_advantage": 1 if (senior and r.random() < 0.8) else 0,
            "age_band": "65+" if senior else "18-64",
        }
        meets = r.random() < SPEC.probability(x)
        if r.random() < shift:
            x.update(conservative_weeks=r.randint(60, 120), doc_score=0.3)
            meets = False  # long, poorly documented histories: a new referral pattern
        note = (
            f"{r.choice(PROCEDURES)} requested. Member MBR-{r.randint(100000, 999999)}, MRN {r.randint(1000000, 9999999)}, "
            f"DOB: {r.randint(1, 12)}/{r.randint(1, 28)}/{r.randint(1940, 2000)}. {x['conservative_weeks']} weeks of therapy."
        )
        out.append({"id": f"PA-{i:05d}", "x": x, "group": x["age_band"], "meets": meets, "untrusted": note})
    return out


def decide(p: float, case: dict) -> str:
    return "approve" if p >= 0.75 else "pend-clinical-review"


def action(decision: str, case: dict):
    if decision == "approve":
        return "approve_request", {"request": case["id"]}
    return "route_to_clinician", {"request": case["id"]}


def evidence(case: dict, decision: str) -> dict[str, str]:
    x = case["x"]
    return {
        "cp-3.1": "coverage policy asks for six or more weeks of documented conservative therapy",
        "cp-3.4": "red-flag findings allow review without the therapy requirement",
        "feat-therapy": f"{x['conservative_weeks']} weeks of conservative therapy documented",
        "feat-docs": f"documentation completeness {x['doc_score']}",
    }


def policy(enforce: bool) -> ToolPolicy:
    return ToolPolicy(allowed={"lookup_policy", "approve_request", "route_to_clinician", "request_records"}, enforce=enforce)


SPEC = AgentSpec(
    id="juniper-prior-auth",
    company="Juniper Health Plan",
    task="prior authorization review",
    features=FEATURES,
    ranges=RANGES,
    weights=WEIGHTS,
    bias=BIAS,
    proxy_weights=PROXIES,
    decide=decide,
    action=action,
    generate=generate,
    label=lambda c: c["meets"],
    positive={"approve"},
    evidence=evidence,
    policy=policy,
    favorable={"approve"},
    hitl_decisions={"pend-clinical-review"},
    mask_kinds=PHI_KINDS,
    notice=NOTICE,
)
