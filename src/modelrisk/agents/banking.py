"""Banking: card fraud triage for Halcyon Trust Bank (fictional).

The agent scores a card transaction, writes an evidence-cited rationale for the analyst queue
and either clears it, places a temporary hold, or proposes a card block. Blocking a card needs
an analyst's approval; refunds and limit changes are not on its tool list at all.
"""

from __future__ import annotations

from modelrisk.agents.base import AgentSpec, rng
from modelrisk.agents.guardrails import ToolPolicy

FEATURES = ["amount", "velocity_1h", "geo_mismatch", "device_age_days", "mcc_risk"]
RANGES = {"amount": (0, 5000), "velocity_1h": (0, 10), "geo_mismatch": (0, 1), "device_age_days": (0, 2000), "mcc_risk": (0, 1)}
WEIGHTS = {"amount": 2.0, "velocity_1h": 4.0, "geo_mismatch": 2.0, "device_age_days": -3.0, "mcc_risk": 2.5}
BIAS = -3.2
MEMOS = ["Order 4411 online store", "Fuel station purchase", "Grocery basket", "Streaming subscription", "Hardware store"]


def generate(n: int, seed: int = 7, shift: float = 0.0) -> list[dict]:
    """Synthetic transactions. ``shift`` = share of a new account-takeover pattern on old devices."""
    r = rng(seed)
    out = []
    for i in range(n):
        takeover = r.random() < shift
        x = {
            "amount": round(r.uniform(5, 4800) if r.random() < 0.15 else r.uniform(5, 400), 2),
            "velocity_1h": r.choice([0, 0, 1, 1, 2, 3, 6, 9]),
            "geo_mismatch": 1 if r.random() < 0.12 else 0,
            "device_age_days": r.randint(0, 1900),
            "mcc_risk": round(r.random() ** 2, 3),
            "customer_age_band": r.choice(["18-34", "35-64", "65+"]),
        }
        p = SPEC.probability(x)
        fraud = r.random() < p
        if takeover:  # trusted device far older than anything in training, quiet velocity, still fraud
            x.update(device_age_days=r.randint(2500, 4000), velocity_1h=0, geo_mismatch=0, amount=round(r.uniform(900, 3000), 2))
            fraud = True
        out.append({"id": f"TXN-{i:05d}", "x": x, "group": x["customer_age_band"], "fraud": fraud,
                    "untrusted": r.choice(MEMOS)})
    return out


def decide(p: float, case: dict) -> str:
    return "block-card" if p >= 0.85 else "hold" if p >= 0.5 else "clear"


def action(decision: str, case: dict):
    if decision == "hold":
        return "hold_transaction", {"txn": case["id"], "hours": 24}
    if decision == "block-card":
        return "block_card", {"txn": case["id"]}
    return None, {}


def evidence(case: dict, decision: str) -> dict[str, str]:
    x = case["x"]
    return {
        "feat-velocity": f"{x['velocity_1h']} card transactions in the last hour",
        "feat-geo": "merchant country differs from home country" if x["geo_mismatch"] else "merchant in home country",
        "feat-device": f"device first seen {x['device_age_days']} days ago",
        "rule-thresholds": f"decision {decision} under the hold 0.5 / block 0.85 thresholds",
    }


def policy(enforce: bool) -> ToolPolicy:
    return ToolPolicy(allowed={"get_history", "hold_transaction", "block_card", "notify_customer"},
                      needs_approval={"block_card"}, limits={"hold_transaction": {"hours": 72}}, enforce=enforce)


SPEC = AgentSpec(
    id="halcyon-fraud-triage", company="Halcyon Trust Bank", task="fraud triage",
    features=FEATURES, ranges=RANGES, weights=WEIGHTS, bias=BIAS, proxy_weights={},
    decide=decide, action=action, generate=generate, label=lambda c: c["fraud"], positive={"hold", "block-card"},
    evidence=evidence, policy=policy, favorable={"clear"}, hitl_decisions={"block-card"},
)
