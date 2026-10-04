"""The CI gate. ``modelrisk gate`` exits non-zero when any of these fail:

    G1 every inventory model has all four pillars
    G2 every artifact validates against its JSON Schema
    G3 every high or critical inherent risk has at least one implemented control
    G4 no scenario breaches its threshold (controls on)
    G5 the pillar links hold (card -> risks, data sheet checks, risks -> scenarios)
    G6 residual risk is within the tier's appetite
    G7 the lifecycle gates up to the current stage pass, with fresh, digest-bound sign-offs
    G8 the sign-off audit chain verifies and the inventory matches the registry folders
"""

from __future__ import annotations

from functools import cache
from typing import Any

from modelrisk import REGISTRY
from modelrisk.combine import risk_coverage, scenario_links, scenario_results, understanding_checks, update_residuals
from modelrisk.lifecycle import stage_status
from modelrisk.registry import ModelRecord, inventory, load_all
from modelrisk.schema import errors
from modelrisk.scoring import score_risk
from modelrisk.signoff import verify_chain
from modelrisk.tiering import eu_ai_act_class, tier
from modelrisk.validation import validate

ARTIFACTS = {"model_card": "model-card", "data_sheet": "data-sheet", "risk_cards": "risk-card",
             "scenarios": "scenario", "approvals": "approvals"}


def validator_of(rec: ModelRecord) -> str | None:
    for s in (rec.approvals or {}).get("signoffs", []):
        if s["role"] == "validator" and s["decision"] == "approve":
            return s["approver"].split(" (")[0]
    return None


@cache
def validation_outcome(model_id: str) -> str:
    from modelrisk.registry import load

    rec = load(model_id)
    who = validator_of(rec)
    return validate(rec, who)["outcome"] if who else "not run"


def check_model(rec: ModelRecord, now: int | None = None) -> dict[str, Any]:
    out: list[dict[str, Any]] = []

    def add(gid: str, ok: bool, detail: str) -> None:
        out.append({"gate": gid, "ok": bool(ok), "detail": detail})

    miss = rec.missing_pillars()
    add("G1-pillars", not miss, "missing: " + ",".join(miss) if miss else "4/4")
    errs = [f"{k}: {e}" for k, kind in ARTIFACTS.items() if getattr(rec, k) is not None for e in errors(kind, getattr(rec, k))]
    add("G2-schemas", not errs, "; ".join(errs[:3]) or "valid")
    if miss or errs:
        return {"model": rec.id, "ok": False, "checks": out}
    bare = [r["id"] for r in rec.risks() if score_risk(r)["inherent"] >= 10 and not score_risk(r)["implemented_controls"]]
    add("G3-high-risk-controls", not bare, "no implemented control: " + ",".join(bare) if bare else "every high/critical risk controlled")
    res = scenario_results(rec)
    br = [f"{r['id']} {r['metric']}={r['value']}" for r in res if r["status"] == "breach"]
    add("G4-scenarios", not br, "breach: " + "; ".join(br) if br else f"{len(res)} scenarios, {sum(r['status'] == 'warn' for r in res)} warn")
    links = [x for x in risk_coverage(rec) if not x["ok"]] + [x for x in understanding_checks(rec) if not x["ok"]] + \
            [x for x in scenario_links(rec) if not x["ok"]]
    add("G5-pillar-links", not links, "; ".join(str(x.get("id") or x.get("kind") or x.get("risk")) for x in links) or "all links hold")
    over = [r["id"] for r in update_residuals(rec, res) if not r["within_appetite"]]
    add("G6-appetite", not over, "over appetite: " + ",".join(over) if over else f"within tier {tier(rec.model_card)} appetite")
    st = stage_status(rec, [r["status"] for r in res], validation_outcome(rec.id), now)
    failed = [f"{c['stage']}: {c['check']}" for c in st["checks"] if not c["ok"]]
    add("G7-lifecycle", st["ok"], "; ".join(failed) or f"stage {rec.stage} gates pass")
    return {"model": rec.id, "ok": all(c["ok"] for c in out), "checks": out, "next_blockers": st["next_blockers"]}


def run_gate(now: int | None = None) -> dict[str, Any]:
    recs = load_all()
    models = [check_model(r, now) for r in recs]
    chain = verify_chain()
    inv_ids = [m["id"] for m in inventory()["models"]]
    folders = sorted(p.name for p in REGISTRY.iterdir() if p.is_dir())
    inv_ok = not errors("inventory", inventory()) and len(set(inv_ids)) == len(inv_ids) and sorted(inv_ids) == folders
    global_checks = [{"gate": "G8-audit-chain", "ok": chain["ok"], "detail": str(chain)},
                     {"gate": "G8-inventory", "ok": inv_ok, "detail": f"{len(inv_ids)} models, {len(folders)} folders"}]
    ok = all(m["ok"] for m in models) and all(c["ok"] for c in global_checks)
    return {"ok": ok, "models": models, "global": global_checks,
            "tiers": {r.id: {"tier": tier(r.model_card), "eu_ai_act": eu_ai_act_class(r.model_card)} for r in recs}}
