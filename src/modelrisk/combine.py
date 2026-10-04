"""How the four pillars combine.

1. model card  -> risk cards   ``required_risks``: what the card implies the risk cards must cover
2. data sheet  -> understanding ``understanding_checks``: the documented inputs, ranges, proxies
                                  and performance match the running model
3. risk cards  -> scenarios    ``scenario_links``: every material risk is exercised by a scenario
                                  that switches its runtime control off
4. scenarios   -> residual risk + backlog ``update_residuals`` / ``backlog``: results change the
                                  credited control effectiveness and create development work
"""

from __future__ import annotations

from functools import cache
from typing import Any

from modelrisk.agents.registry import SPECS
from modelrisk.evaluation import evaluate
from modelrisk.registry import ModelRecord, load
from modelrisk.scenarios.engine import KIND_CONTROLS, run, run_external
from modelrisk.scoring import score_risk, within_appetite
from modelrisk.tiering import tier

# --- 1. model card -> risk cards ---------------------------------------------------------


def required_risks(card: dict[str, Any]) -> list[dict[str, str]]:
    """Scenario families the model card says must be on the risk cards, with the reason."""
    req = [("data-drift", "every statistical model drifts")]
    sysd, impact = card["system"], card["decision_impact"]
    if sysd["type"] == "agentic-llm":
        req += [("prompt-injection", "an LLM reads untrusted text"), ("model-outage", "depends on a hosted model")]
        if impact["affects_individuals"]:
            req.append(("hallucination", "a generated rationale reaches decisions about people"))
    if sysd["autonomy"] in ("act", "act-with-approval") and sysd["tools"]:
        req.append(("tool-misuse", f"autonomy is {sysd['autonomy']} with tools"))
    if set(card["data_sensitivity"]) & {"pii", "phi"}:
        req.append(("pii-leak", "processes " + "/".join(sorted(set(card["data_sensitivity"]) & {"pii", "phi"}))))
    if card["fairness"]["protected_attributes"]:
        req.append(("bias", "fairness section names protected attributes"))
    if card.get("monthly_volume", 0) >= 100_000:
        req.append(("cost-spike", "monthly volume of 100,000 or more"))
    return [{"kind": k, "reason": r} for k, r in req]


def risk_coverage(rec: ModelRecord) -> list[dict[str, Any]]:
    if rec.kind == "portfolio":
        return [{"kind": "external", "reason": "portfolio component", "covered_by": [s["id"] for s in rec.scenario_list()],
                 "ok": bool(rec.scenario_list())}]
    kinds: dict[str, list[str]] = {}
    for s in rec.scenario_list():
        kinds.setdefault(s["kind"], []).extend(s["risk_ids"])
    out = []
    for r in required_risks(rec.model_card):
        covered = sorted(set(kinds.get(r["kind"], [])))
        out.append({**r, "covered_by": covered, "ok": bool(covered)})
    return out


# --- 2. data sheet -> model understanding ------------------------------------------------


@cache
def _eval(model_id: str, seed: int) -> dict[str, Any]:
    return evaluate(SPECS[model_id], seed=seed)


def understanding_checks(rec: ModelRecord) -> list[dict[str, Any]]:
    sheet, card = rec.data_sheet, rec.model_card
    checks: list[dict[str, Any]] = []

    def add(cid: str, ok: bool, detail: str) -> None:
        checks.append({"id": cid, "ok": bool(ok), "detail": detail})

    inputs = {i["name"]: i for i in sheet["inputs"]}
    add("DS1-inputs-documented", bool(inputs), f"{len(inputs)} inputs documented")
    add("DS2-synthetic-declared", sheet["training_data"]["synthetic"], "training data declared synthetic")
    if rec.kind == "portfolio":
        return checks
    spec = SPECS[rec.id]
    used = {n for n, i in inputs.items() if i["used_by_model"]}
    add("DS3-features-match", used == set(spec.features), f"data sheet {sorted(used)} vs model {sorted(spec.features)}")
    bad_range = [f for f in spec.features if f in inputs and tuple(inputs[f].get("range", ())) != tuple(spec.ranges[f])]
    add("DS4-ranges-match", not bad_range, "ranges differ: " + ",".join(bad_range) if bad_range else "all ranges match")
    leaked = [n for n, i in inputs.items() if i["sensitivity"] == "protected" and i["used_by_model"]]
    add("DS5-protected-not-used", not leaked, "protected inputs used: " + ",".join(leaked) if leaked else "no protected input reaches the model")
    undocumented = [p for p in spec.proxy_weights if p not in inputs or inputs[p]["sensitivity"] != "protected"]
    add("DS6-proxies-documented", not undocumented, "proxies not documented as protected: " + ",".join(undocumented)
        if undocumented else f"{len(spec.proxy_weights)} known proxies documented and excluded")
    ref = _eval(rec.id, 7)
    outside = [f for f in spec.features if not all(spec.ranges[f][0] <= v <= spec.ranges[f][1] for v in ref["features"][f])]
    add("DS7-training-in-range", not outside, "reference data outside documented range: " + ",".join(outside) if outside else "reference data inside every range")
    val = _eval(rec.id, 11)
    drift = [p["metric"] for p in sheet["performance"]
             if abs(p["train"] - ref[p["metric"]]) > 0.02 or abs(p["validation"] - val[p["metric"]]) > 0.02]
    add("DS8-performance-reproduces", not drift, "not reproduced: " + ",".join(drift) if drift else "train and validation figures reproduce within 0.02")
    card_vals = {m["name"]: m["value"] for m in card["metrics"]}
    mismatch = [p["metric"] for p in sheet["performance"] if p["metric"] in card_vals and abs(card_vals[p["metric"]] - p["train"]) > 0.02]
    add("DS9-card-matches-sheet", not mismatch, "model card and data sheet disagree: " + ",".join(mismatch) if mismatch else "model card metrics match the data sheet")
    return checks


# --- 3. risk cards -> scenarios ----------------------------------------------------------


def scenario_links(rec: ModelRecord) -> list[dict[str, Any]]:
    risks = {r["id"]: r for r in rec.risks()}
    scen = {s["id"]: s for s in rec.scenario_list()}
    out = []
    for r in risks.values():
        material = r["likelihood"] * r["impact"] >= 10
        linked = [s for s in r["scenarios"] if s in scen]
        dangling = [s for s in r["scenarios"] if s not in scen]
        ok = (bool(linked) or not material) and not dangling
        out.append({"risk": r["id"], "material": material, "scenarios": linked, "ok": ok,
                    "detail": "dangling: " + ",".join(dangling) if dangling else ("no scenario for a material risk" if not ok else "linked")})
    for s in scen.values():
        missing = [rid for rid in s["risk_ids"] if rid not in risks]
        if missing:
            out.append({"risk": ",".join(missing), "material": True, "scenarios": [s["id"]], "ok": False, "detail": "scenario cites unknown risk"})
        elif s["kind"] != "external" and rec.kind == "domain":
            ctl = {c.get("runtime_control") for rid in s["risk_ids"] for c in risks[rid]["controls"]}
            if not ctl & set(KIND_CONTROLS[s["kind"]]):
                out.append({"risk": ",".join(s["risk_ids"]), "material": True, "scenarios": [s["id"]], "ok": False,
                            "detail": f"no linked control implements {KIND_CONTROLS[s['kind']]}"})
    return out


# --- 4. scenario results -> residual risk + backlog --------------------------------------


@cache
def _scenario(model_id: str, scenario_id: str, mitigations: bool) -> dict[str, Any]:
    rec = load(model_id)
    s = next(x for x in rec.scenario_list() if x["id"] == scenario_id)
    if s["kind"] == "external":
        return run_external(s)
    return run(SPECS[model_id], s, rec.risks(), mitigations=mitigations)


def scenario_results(rec: ModelRecord, mitigations: bool = True) -> list[dict[str, Any]]:
    return [_scenario(rec.id, s["id"], mitigations) for s in rec.scenario_list()]


CREDIT = {"pass": 1.0, "warn": 0.5, "breach": 0.0}


def update_residuals(rec: ModelRecord, results: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Re-score each risk with control credit adjusted by the scenarios that exercise it."""
    results = results if results is not None else scenario_results(rec)
    t = tier(rec.model_card)
    worst: dict[str, str] = {}
    order = ["pass", "warn", "breach"]
    for res in results:
        for rid in res["risk_ids"]:
            if order.index(res["status"]) >= order.index(worst.get(rid, "pass")):
                worst[rid] = res["status"]
    out = []
    for r in rec.risks():
        before = score_risk(r)
        credit = CREDIT[worst.get(r["id"], "pass")]
        overrides = {c["id"]: c["effectiveness"] * credit for c in r["controls"]
                     if c.get("runtime_control") or rec.kind == "portfolio"}
        after = score_risk(r, overrides)
        out.append({**after, "residual_before": before["residual"], "scenario_status": worst.get(r["id"], "not-tested"),
                    "within_appetite": within_appetite(after["residual_band"], t)})
    return out


def backlog(rec: ModelRecord, results: list[dict[str, Any]] | None = None,
            what_if: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    """Development backlog generated from scenario results, what-ifs and the risk cards."""
    results = results if results is not None else scenario_results(rec)
    what_if = what_if if what_if is not None else (scenario_results(rec, mitigations=False) if rec.kind == "domain" else [])
    items: list[dict[str, str]] = []
    for res in results:
        if res["status"] == "breach":
            items.append({"priority": "P1", "source": res["id"], "item": f"Fix: {res['metric']} {res['value']} breaches {res['threshold']}; block promotion"})
        elif res["status"] == "warn":
            items.append({"priority": "P2", "source": res["id"], "item": f"Tune: {res['metric']} {res['value']} is inside the warn band ({res['threshold']})"})
    for res in what_if:
        if res["status"] == "pass":
            items.append({"priority": "P3", "source": res["id"],
                          "item": f"Strengthen scenario: still passes with {res['mitigations']}, so it does not prove the control is needed"})
    for r in rec.risks():
        for c in r["controls"]:
            if c["status"] == "planned":
                items.append({"priority": "P2", "source": c["id"], "item": f"Implement planned control for {r['id']}: {c['description']}"})
    for r in update_residuals(rec, results):
        if not r["within_appetite"]:
            items.append({"priority": "P1", "source": r["id"], "item": f"Residual {r['residual']} ({r['residual_band']}) exceeds tier appetite; add controls or record acceptance"})
    return items


def summary(rec: ModelRecord) -> dict[str, Any]:
    results = scenario_results(rec)
    return {
        "model": rec.id,
        "1_model_card_to_risks": risk_coverage(rec),
        "2_data_sheet_understanding": understanding_checks(rec),
        "3_risks_to_scenarios": scenario_links(rec),
        "4_residuals": update_residuals(rec, results),
        "4_backlog": backlog(rec, results),
    }
