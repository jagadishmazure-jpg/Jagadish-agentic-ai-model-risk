"""Independent validation (effective challenge).

The validator re-performs the developer's work instead of reading it: fresh synthetic data on a
different seed, the full scenario suite, the data-sheet understanding checks and a naive
challenger. Findings carry a severity; any high finding fails validation.

    V1 independence        validator is not the developer team or the model owner
    V2 conceptual          limitations, out-of-scope uses, fallback and thresholds documented
    V3 re-performance      card metrics reproduce on seed 11 within 0.05
    V4 outcomes            seed-11 metrics meet the card thresholds
    V5 challenger          balanced accuracy beats a naive challenger (0.5)
    V6 scenarios           no breach with controls on
    V7 data understanding  every data-sheet check passes
"""

from __future__ import annotations

from typing import Any

from modelrisk.agents.registry import SPECS
from modelrisk.combine import _eval, scenario_results, understanding_checks
from modelrisk.registry import ModelRecord

TOLERANCE = 0.05
VALIDATION_SEED = 11


def _finding(fid: str, ok: bool, severity: str, detail: str) -> dict[str, Any]:
    return {"id": fid, "ok": bool(ok), "severity": "none" if ok else severity, "detail": detail}


def validate(rec: ModelRecord, validator: str, team: str = "Independent Validation") -> dict[str, Any]:
    card = rec.model_card
    f: list[dict[str, Any]] = []
    indep = team.lower() not in card["developer"].lower() and validator.lower() not in card["owner"].lower()
    f.append(_finding("V1-independence", indep, "high", f"{validator} ({team}) vs developer {card['developer']}"))
    concept = bool(card["limitations"]) and bool(card["out_of_scope_uses"]) and bool(card["system"]["fallback"])
    f.append(_finding("V2-conceptual-soundness", concept, "medium", "limitations, out-of-scope uses and fallback documented"))
    if rec.kind == "domain":
        spec = SPECS[rec.id]
        fresh = _eval(rec.id, VALIDATION_SEED)
        gaps = [f"{m['name']} card {m['value']} vs {fresh[m['name']]}" for m in card["metrics"] if abs(m["value"] - fresh[m["name"]]) > TOLERANCE]
        f.append(_finding("V3-re-performance", not gaps, "high", "; ".join(gaps) or f"all card metrics reproduce on seed {VALIDATION_SEED}"))
        below = [
            f"{m['name']} {fresh[m['name']]} < {m['threshold']}"
            for m in card["metrics"]
            if (fresh[m["name"]] < m["threshold"] if m["direction"] == "higher-is-better" else fresh[m["name"]] > m["threshold"])
        ]
        f.append(_finding("V4-outcomes", not below, "high", "; ".join(below) or "all metrics meet thresholds on fresh data"))
        bal = round((fresh["recall"] + _specificity(spec)) / 2, 4)
        f.append(_finding("V5-challenger", bal > 0.5, "medium", f"balanced accuracy {bal} vs naive challenger 0.5"))
        dsc = [c["id"] for c in understanding_checks(rec) if not c["ok"]]
        f.append(_finding("V7-data-understanding", not dsc, "high", ",".join(dsc) or "all data-sheet checks pass"))
    else:
        f.append(_finding("V3-re-performance", True, "low", "re-performed in the source repository's CI (attested)"))
    res = scenario_results(rec)
    breaches = [r["id"] for r in res if r["status"] == "breach"]
    warns = [r["id"] for r in res if r["status"] == "warn"]
    f.append(_finding("V6-scenarios", not breaches, "high", f"breaches {breaches}" if breaches else f"{len(res)} scenarios, warn {warns}"))
    if warns:
        f.append(_finding("V6-warn-band", False, "low", f"inside warn band: {warns}"))
    high = [x for x in f if x["severity"] == "high"]
    other = [x for x in f if x["severity"] in ("medium", "low")]
    outcome = "fail" if high else "pass-with-findings" if other else "pass"
    return {"model": rec.id, "validator": validator, "team": team, "outcome": outcome, "findings": f}


def _specificity(spec) -> float:
    e = _eval(spec.id, VALIDATION_SEED)
    return e["specificity"]
