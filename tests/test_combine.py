import pytest

from modelrisk.combine import (
    backlog,
    required_risks,
    risk_coverage,
    scenario_links,
    understanding_checks,
    update_residuals,
)
from tests.conftest import DOMAIN_IDS, PORTFOLIO_IDS


@pytest.mark.parametrize("model_id", DOMAIN_IDS + PORTFOLIO_IDS)
def test_all_four_links_hold(records, model_id):
    rec = records[model_id]
    assert all(x["ok"] for x in risk_coverage(rec))
    assert all(x["ok"] for x in understanding_checks(rec))
    assert all(x["ok"] for x in scenario_links(rec))


def test_model_card_implies_risks(records):
    kinds = {r["kind"] for r in required_risks(records["juniper-prior-auth"].model_card)}
    assert kinds == {"data-drift", "prompt-injection", "model-outage", "hallucination", "tool-misuse", "pii-leak", "bias", "cost-spike"}


def test_retail_needs_no_pii_scenario(records):
    kinds = {r["kind"] for r in required_risks(records["marigold-pricing-demand"].model_card)}
    assert "pii-leak" not in kinds and "prompt-injection" in kinds


def test_missing_risk_is_detected(fresh):
    rec = fresh("marigold-pricing-demand")
    rec.scenarios["scenarios"] = [s for s in rec.scenarios["scenarios"] if s["kind"] != "prompt-injection"]
    missing = [x for x in risk_coverage(rec) if not x["ok"]]
    assert [x["kind"] for x in missing] == ["prompt-injection"]


def test_data_sheet_range_mismatch_is_detected(fresh):
    rec = fresh("halcyon-fraud-triage")
    rec.data_sheet["inputs"][0]["range"] = [0, 99]
    assert not next(c for c in understanding_checks(rec) if c["id"] == "DS4-ranges-match")["ok"]


def test_protected_input_marked_as_used_is_detected(fresh):
    rec = fresh("cedarhollow-underwriting-assistant")
    for i in rec.data_sheet["inputs"]:
        if i["name"] == "tract_minority_share":
            i["used_by_model"] = True
    failed = {c["id"] for c in understanding_checks(rec) if not c["ok"]}
    assert {"DS3-features-match", "DS5-protected-not-used"} <= failed


def test_undocumented_proxy_is_detected(fresh):
    rec = fresh("bramblewood-claims-triage")
    rec.data_sheet["inputs"] = [i for i in rec.data_sheet["inputs"] if i["name"] != "zip_risk_index"]
    assert not next(c for c in understanding_checks(rec) if c["id"] == "DS6-proxies-documented")["ok"]


def test_overstated_performance_is_detected(fresh):
    rec = fresh("juniper-prior-auth")
    rec.data_sheet["performance"][0]["train"] = 0.99
    failed = {c["id"] for c in understanding_checks(rec) if not c["ok"]}
    assert {"DS8-performance-reproduces", "DS9-card-matches-sheet"} <= failed


def test_material_risk_without_scenario_is_detected(fresh):
    rec = fresh("halcyon-fraud-triage")
    rec.risk_cards["risks"][0]["scenarios"] = []
    assert any(not x["ok"] and x["risk"] == "BNK-R1" for x in scenario_links(rec))


def test_scenario_citing_unknown_risk_is_detected(fresh):
    rec = fresh("halcyon-fraud-triage")
    rec.scenarios["scenarios"][0]["risk_ids"] = ["BNK-R99"]
    assert any(x["detail"] == "scenario cites unknown risk" for x in scenario_links(rec))


def test_scenario_whose_risk_lacks_the_runtime_control_is_detected(fresh):
    rec = fresh("halcyon-fraud-triage")
    for c in rec.risk_cards["risks"][1]["controls"]:
        c.pop("runtime_control", None)
    assert any("no linked control implements" in x["detail"] for x in scenario_links(rec))


def _fake(rid, st):
    return [{"id": "S", "status": st, "risk_ids": [rid], "metric": "m", "value": 1, "threshold": "<= 0", "mitigations": "on"}]


def test_breach_removes_control_credit(records):
    rec = records["halcyon-fraud-triage"]
    r1 = next(r for r in update_residuals(rec, _fake("BNK-R1", "breach")) if r["id"] == "BNK-R1")
    assert r1["residual"] > r1["residual_before"] and r1["scenario_status"] == "breach"


def test_warn_halves_control_credit(records):
    rec = records["halcyon-fraud-triage"]
    warn = next(r for r in update_residuals(rec, _fake("BNK-R4", "warn")) if r["id"] == "BNK-R4")
    assert warn["control_effectiveness"] == 0.35


def test_breach_creates_a_p1_backlog_item_and_appetite_breach(records):
    items = backlog(records["halcyon-fraud-triage"], _fake("BNK-R1", "breach"), [])
    assert any(i["priority"] == "P1" and i["source"] == "S" for i in items)
    assert any(i["priority"] == "P1" and i["source"] == "BNK-R1" for i in items)


def test_backlog_lists_planned_controls_and_weak_scenarios(records):
    items = backlog(records["halcyon-fraud-triage"])
    sources = {i["source"] for i in items}
    assert {"BNK-C3", "BNK-C13", "BNK-S7"} <= sources


def test_warn_band_reaches_the_backlog(records):
    assert any(i["source"] == "HC-S7" and i["priority"] == "P2" for i in backlog(records["juniper-prior-auth"]))
