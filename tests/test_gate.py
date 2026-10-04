from modelrisk.gate import check_model


def failed(result):
    return {c["gate"] for c in result["checks"] if not c["ok"]}


def test_gate_passes_on_the_checked_in_registry(gate):
    assert gate["ok"], [(m["model"], failed(m)) for m in gate["models"] if not m["ok"]]


def test_gate_covers_every_model(gate):
    assert len(gate["models"]) == 10 and all(len(m["checks"]) == 7 for m in gate["models"])


def test_gate_global_checks(gate):
    assert {c["gate"] for c in gate["global"]} == {"G8-audit-chain", "G8-inventory"} and all(c["ok"] for c in gate["global"])


def test_missing_pillar_fails(fresh):
    rec = fresh("marigold-pricing-demand")
    rec.data_sheet = None
    assert "G1-pillars" in failed(check_model(rec))


def test_schema_error_fails(fresh):
    rec = fresh("marigold-pricing-demand")
    rec.model_card["version"] = "one"
    assert "G2-schemas" in failed(check_model(rec))


def test_high_risk_without_implemented_control_fails(fresh):
    rec = fresh("halcyon-fraud-triage")
    for c in rec.risk_cards["risks"][1]["controls"]:
        c["status"] = "planned"
    assert "G3-high-risk-controls" in failed(check_model(rec))


def test_scenario_breach_fails(fresh):
    rec = fresh("halcyon-fraud-triage")
    rec.scenarios["scenarios"][3]["threshold"] = {"op": ">=", "value": 2.0}
    assert "G4-scenarios" in failed(check_model(rec))


def test_broken_link_fails(fresh):
    rec = fresh("marigold-pricing-demand")
    rec.scenarios["scenarios"] = [s for s in rec.scenarios["scenarios"] if s["kind"] != "prompt-injection"]
    for r in rec.risk_cards["risks"]:
        r["scenarios"] = [s for s in r["scenarios"] if s != "RTL-S7"]
    assert "G5-pillar-links" in failed(check_model(rec))


def test_residual_over_appetite_fails(fresh):
    rec = fresh("halcyon-fraud-triage")
    rec.risk_cards["risks"][0]["controls"][0]["effectiveness"] = 0.05
    rec.risk_cards["risks"][0]["controls"][1]["effectiveness"] = 0.05
    assert "G6-appetite" in failed(check_model(rec))


def test_any_edit_without_new_signoffs_fails_the_lifecycle_gate(fresh):
    rec = fresh("bramblewood-claims-triage")
    rec.model_card["limitations"].append("A new limitation nobody signed off.")
    assert failed(check_model(rec)) == {"G7-lifecycle"}
