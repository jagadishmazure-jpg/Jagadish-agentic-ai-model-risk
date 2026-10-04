import pytest

from modelrisk.combine import run_scenario, scenario_results
from modelrisk.registry import load_all
from modelrisk.scenarios.engine import KIND_CONTROLS, controls_for, psi, status

ALL = [(r.id, s["id"]) for r in load_all() for s in r.scenario_list()]
DOMAIN = [(r.id, s["id"]) for r in load_all() if r.kind == "domain" for s in r.scenario_list()]
# What-ifs that still pass with controls off: banking has no age proxy to remove (P3 backlog item).
NOT_LOAD_BEARING = {"BNK-S7"}


def _get(records, mid, sid):
    rec = records[mid]
    return rec, next(s for s in rec.scenario_list() if s["id"] == sid)


@pytest.mark.parametrize("mid,sid", ALL)
def test_scenario_meets_its_threshold_with_controls_on(records, mid, sid):
    rec, s = _get(records, mid, sid)
    assert run_scenario(rec, s)["status"] in ("pass", "warn")


@pytest.mark.parametrize("mid,sid", [x for x in DOMAIN if x[1] not in NOT_LOAD_BEARING])
def test_switching_the_linked_controls_off_breaches(records, mid, sid):
    rec, s = _get(records, mid, sid)
    assert run_scenario(rec, s, mitigations=False)["status"] == "breach"


def test_all_eight_families_are_covered(records):
    kinds = {s["kind"] for r in records.values() for s in r.scenario_list()}
    assert set(KIND_CONTROLS) <= kinds


def test_portfolio_scenarios_are_external_with_evidence(records):
    for r in records.values():
        if r.kind == "portfolio":
            assert all(s["kind"] == "external" and s["evidence"].startswith("https://github.com/") for s in r.scenario_list())


def test_mortgage_fair_lending_results(records):
    res = {r["id"]: r for r in scenario_results(records["cedarhollow-underwriting-assistant"])}
    assert res["MTG-S1"]["value"] >= 0.8 and res["MTG-S2"]["value"] == 0.0


def test_mortgage_proxy_what_if_shows_disparate_impact(records):
    rec, s = _get(records, "cedarhollow-underwriting-assistant", "MTG-S1")
    off = run_scenario(rec, s, mitigations=False)
    assert off["value"] < 0.8 and off["details"]["favorable_rate_by_group"]["B"] < off["details"]["favorable_rate_by_group"]["A"]


def test_healthcare_cost_scenario_is_in_the_warn_band(records):
    rec, s = _get(records, "juniper-prior-auth", "HC-S7")
    assert run_scenario(rec, s)["status"] == "warn"


def test_controls_for_uses_the_risk_card_runtime_controls(records):
    rec, s = _get(records, "halcyon-fraud-triage", "BNK-S1")
    assert controls_for(s, rec.risks()) == ["ood_guard"]


def test_controls_for_falls_back_to_the_family_default():
    s = {"risk_ids": ["X"], "kind": "pii-leak"}
    assert controls_for(s, []) == ["mask_output"]


def test_psi_is_zero_for_identical_samples_and_grows_with_shift():
    ref = [i / 100 for i in range(100)]
    assert psi(ref, ref) == 0.0
    assert psi(ref, [v + 0.5 for v in ref]) > 0.25


@pytest.mark.parametrize("value,op,thr,warn,expected", [
    (0.0, "<=", 0.0, None, "pass"), (0.1, "<=", 0.0, None, "breach"), (0.04, "<=", 0.05, 0.03, "warn"),
    (0.95, ">=", 0.8, 0.9, "pass"), (0.85, ">=", 0.8, 0.9, "warn"), (0.7, ">=", 0.8, 0.9, "breach"),
])
def test_status(value, op, thr, warn, expected):
    assert status(value, {"op": op, "value": thr}, warn) == expected


def test_drift_details_report_psi_and_routing(records):
    rec, s = _get(records, "halcyon-fraud-triage", "BNK-S1")
    d = run_scenario(rec, s)["details"]
    assert d["psi_score"] > 0.25 and d["flagged_out_of_range"] > 0


def test_cost_spike_respects_the_budget(records):
    rec, s = _get(records, "marigold-pricing-demand", "RTL-S2")
    r = run_scenario(rec, s)
    assert r["value"] <= 0.05 and r["details"]["budget_tokens"] == 4000
