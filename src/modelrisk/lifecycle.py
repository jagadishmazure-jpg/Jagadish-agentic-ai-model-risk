"""Lifecycle stages and approval gates.

    development -> validation -> production -> monitoring -> retired
                      ^                            |
                      +---- breach or alert -------+

Each gate is a list of checks. A model's *current* stage is healthy only if every gate up to
and including it passes. The sign-offs a gate needs depend on the inventory tier.
"""

from __future__ import annotations

from typing import Any

from modelrisk.registry import ModelRecord
from modelrisk.schema import errors
from modelrisk.signoff import valid_signoffs
from modelrisk.tiering import tier

STAGES = ["development", "validation", "production", "monitoring", "retired"]

# Roles that must approve entry into each stage, by tier.
REQUIRED_ROLES: dict[str, dict[int, list[str]]] = {
    "validation": {1: ["model-owner"], 2: ["model-owner"], 3: ["model-owner"]},
    "production": {1: ["validator", "model-risk", "business-owner", "compliance"],
                   2: ["validator", "model-risk", "business-owner"], 3: ["validator", "business-owner"]},
    "monitoring": {1: ["model-risk"], 2: ["model-owner"], 3: ["model-owner"]},
    "retired": {1: ["model-owner", "model-risk"], 2: ["model-owner", "model-risk"], 3: ["model-owner"]},
}


def extra_roles(rec: ModelRecord, stage: str) -> list[str]:
    """Domain-specific approvers on top of the tier defaults."""
    if stage != "production" or rec.kind != "domain":
        return []
    roles = []
    if "phi" in rec.model_card["data_sensitivity"]:
        roles += ["privacy", "clinical-reviewer"]
    return roles


def required_roles(rec: ModelRecord, stage: str) -> list[str]:
    return REQUIRED_ROLES[stage][tier(rec.model_card)] + extra_roles(rec, stage)


def gate_checks(rec: ModelRecord, stage: str, scenario_status: list[str] | None = None,
                validation_outcome: str | None = None, now: int | None = None) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"stage": stage, "check": name, "ok": bool(ok), "detail": detail})

    if stage == "validation":
        miss = rec.missing_pillars()
        add("four pillars present", not miss, ",".join(miss) or "model card, data sheet, risk cards, scenarios")
        kinds = {"model_card": "model-card", "data_sheet": "data-sheet", "risk_cards": "risk-card", "scenarios": "scenario"}
        errs = [f"{k}: {e}" for k, kind in kinds.items() if getattr(rec, k) for e in errors(kind, getattr(rec, k))]
        add("schemas valid", not errs, "; ".join(errs[:3]))
    if stage == "production":
        add("independent validation passed", validation_outcome in ("pass", "pass-with-findings"), validation_outcome or "not run")
        breaches = [s for s in (scenario_status or []) if s == "breach"]
        add("no scenario breaches", not breaches, f"{len(breaches)} breach(es)")
    if stage == "monitoring":
        mon = (rec.model_card or {}).get("monitoring", {})
        add("monitoring thresholds defined", bool(mon.get("performance")) and mon.get("psi_alert", 0) > mon.get("psi_warn", 1),
            f"psi warn {mon.get('psi_warn')} / alert {mon.get('psi_alert')}")
    if stage == "retired":
        add("fallback documented", bool(rec.model_card["system"]["fallback"]), rec.model_card["system"]["fallback"])
    have = valid_signoffs(rec, stage, now)
    for role in required_roles(rec, stage):
        add(f"sign-off: {role}", role in have, have[role]["approver"] if role in have else "missing or stale")
    return checks


def stage_status(rec: ModelRecord, scenario_status: list[str], validation_outcome: str, now: int | None = None) -> dict[str, Any]:
    """Checks for every gate up to the current stage, plus the next gate (informational)."""
    idx = STAGES.index(rec.stage)
    path = [s for s in STAGES[1: idx + 1] if s != "retired" or rec.stage == "retired"]
    current = [c for s in path for c in gate_checks(rec, s, scenario_status, validation_outcome, now)]
    nxt = STAGES[idx + 1] if idx + 1 < len(STAGES) and rec.stage != "monitoring" else None
    upcoming = gate_checks(rec, nxt, scenario_status, validation_outcome, now) if nxt else []
    return {"model": rec.id, "stage": rec.stage, "tier": tier(rec.model_card), "ok": all(c["ok"] for c in current),
            "checks": current, "next_stage": nxt, "next_blockers": [c for c in upcoming if not c["ok"]]}
