import pytest

from modelrisk.combine import scenario_results
from modelrisk.gate import validation_outcome
from modelrisk.lifecycle import STAGES, gate_checks, required_roles, stage_status
from modelrisk.monitoring import monitor
from modelrisk.validation import validate
from tests.conftest import ALL_IDS, DOMAIN_IDS


def test_stage_order():
    assert STAGES == ["development", "validation", "production", "monitoring", "retired"]


@pytest.mark.parametrize("model_id", ALL_IDS)
def test_current_stage_gates_pass(records, model_id):
    rec = records[model_id]
    st = stage_status(rec, [r["status"] for r in scenario_results(rec)], validation_outcome(model_id))
    assert st["ok"], [c for c in st["checks"] if not c["ok"]]


def test_tier_one_production_needs_four_approvers(records):
    assert required_roles(records["halcyon-fraud-triage"], "production") == ["validator", "model-risk", "business-owner", "compliance"]


def test_phi_models_add_privacy_and_clinical_review(records):
    roles = required_roles(records["juniper-prior-auth"], "production")
    assert {"privacy", "clinical-reviewer"} <= set(roles)


def test_tier_three_still_needs_a_validator(records):
    assert "validator" in required_roles(records["pff-finops-agent"], "production")


def test_mortgage_is_blocked_on_compliance(records):
    rec = records["cedarhollow-underwriting-assistant"]
    st = stage_status(rec, [r["status"] for r in scenario_results(rec)], "pass")
    assert st["next_stage"] == "production" and [c["check"] for c in st["next_blockers"]] == ["sign-off: compliance"]


def test_healthcare_is_blocked_on_compliance_and_clinical_review(records):
    rec = records["juniper-prior-auth"]
    st = stage_status(rec, [r["status"] for r in scenario_results(rec)], "pass")
    assert {c["check"] for c in st["next_blockers"]} == {"sign-off: compliance", "sign-off: clinical-reviewer"}


def test_production_gate_fails_on_a_breach(records):
    checks = gate_checks(records["bramblewood-claims-triage"], "production", ["pass", "breach"], "pass")
    assert not next(c for c in checks if c["check"] == "no scenario breaches")["ok"]


def test_production_gate_fails_without_validation(records):
    checks = gate_checks(records["bramblewood-claims-triage"], "production", ["pass"], "fail")
    assert not next(c for c in checks if c["check"] == "independent validation passed")["ok"]


def test_retirement_gate_checks_fallback_and_signoffs(records):
    checks = gate_checks(records["halcyon-fraud-triage"], "retired", [], "pass")
    assert next(c for c in checks if c["check"] == "fallback documented")["ok"]
    assert not next(c for c in checks if c["check"] == "sign-off: model-risk")["ok"]


@pytest.mark.parametrize("model_id", ALL_IDS)
def test_independent_validation_does_not_fail(records, model_id):
    assert validate(records[model_id], "Iris Delgado")["outcome"] in ("pass", "pass-with-findings")


def test_validator_from_the_developer_team_is_a_high_finding(records):
    v = validate(records["halcyon-fraud-triage"], "Ana", team="Fraud Data Science team")
    assert v["outcome"] == "fail" and v["findings"][0]["severity"] == "high"


def test_owner_cannot_validate(records):
    v = validate(records["halcyon-fraud-triage"], "Rhea Castellano")
    assert v["outcome"] == "fail"


def test_overstated_card_metric_fails_re_performance(fresh):
    rec = fresh("marigold-pricing-demand")
    rec.model_card["metrics"][0]["value"] = 0.99
    v = validate(rec, "Iris Delgado")
    assert not next(f for f in v["findings"] if f["id"] == "V3-re-performance")["ok"]


def test_warn_band_is_a_low_finding(records):
    v = validate(records["juniper-prior-auth"], "Iris Delgado")
    assert v["outcome"] == "pass-with-findings" and any(f["id"] == "V6-warn-band" for f in v["findings"])


@pytest.mark.parametrize("model_id", DOMAIN_IDS)
def test_monitoring_alerts_on_drift(records, model_id):
    assert monitor(records[model_id], shift=0.3)["status"] == "alert"


@pytest.mark.parametrize("model_id", ["halcyon-fraud-triage", "bramblewood-claims-triage", "marigold-pricing-demand"])
def test_monitoring_is_quiet_on_a_normal_window(records, model_id):
    assert monitor(records[model_id])["status"] == "ok"


def test_monitoring_alert_triggers_the_card_action(records):
    m = monitor(records["halcyon-fraud-triage"], shift=0.3)
    assert m["action"] == records["halcyon-fraud-triage"].model_card["monitoring"]["on_alert"]


def test_portfolio_components_are_monitored_externally(records):
    assert monitor(records["pff-finops-agent"])["status"] == "external"
