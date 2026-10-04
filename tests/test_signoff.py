import pytest

from modelrisk.signoff import (
    MAX_AGE_DAYS,
    SignoffRefused,
    append,
    digest,
    read_log,
    request,
    sign,
    stale_signoffs,
    valid_signoffs,
    verify_chain,
)


def test_checked_in_audit_chain_verifies():
    v = verify_chain()
    assert v["ok"] and v["entries"] > 40


def test_checked_in_signoffs_are_fresh(records):
    assert all(not stale_signoffs(r) for r in records.values())


def test_digest_ignores_approvals_but_tracks_pillars(fresh):
    rec = fresh("halcyon-fraud-triage")
    before = digest(rec)
    rec.approvals = {"model_id": rec.id, "signoffs": []}
    assert digest(rec) == before
    rec.model_card["purpose"] += " (edited)"
    assert digest(rec) != before


def test_editing_a_card_makes_signoffs_stale(fresh):
    rec = fresh("halcyon-fraud-triage")
    rec.risk_cards["risks"][0]["likelihood"] = 5
    assert stale_signoffs(rec) and not valid_signoffs(rec, "production")


def test_signoffs_expire(records):
    rec = records["halcyon-fraud-triage"]
    later = rec.approvals["signoffs"][0]["signed_epoch"] + (MAX_AGE_DAYS + 1) * 86400
    assert valid_signoffs(rec, "production", now=later) == {}


def test_sign_and_request_append_to_a_chain(tmp_path, fresh):
    log = tmp_path / "audit.jsonl"
    rec = fresh("bramblewood-claims-triage")
    request(rec, "monitoring", "Tomas Albright", now=1, log=log)
    s = sign(
        rec,
        "monitoring",
        "model-risk",
        "Marcus Feld (Model Risk Management)",
        "approve",
        "Monitoring evidence reviewed.",
        now=2,
        log=log,
        write=False,
    )
    assert len(read_log(log)) == 2 and s["audit_hash"] == read_log(log)[-1]["hash"] and verify_chain(log)["ok"]


def test_self_signoff_is_refused(tmp_path, fresh):
    with pytest.raises(SignoffRefused):
        sign(
            fresh("halcyon-fraud-triage"),
            "production",
            "model-risk",
            "Fraud Data Science team",
            "approve",
            "Looks fine to us.",
            log=tmp_path / "a",
            write=False,
        )


def test_owner_cannot_be_validator(tmp_path, fresh):
    with pytest.raises(SignoffRefused):
        sign(
            fresh("halcyon-fraud-triage"),
            "production",
            "validator",
            "Rhea Castellano (Head of Fraud Strategy)",
            "approve",
            "Validated it myself.",
            log=tmp_path / "a",
            write=False,
        )


def test_rationale_is_required(tmp_path, fresh):
    with pytest.raises(SignoffRefused):
        sign(fresh("halcyon-fraud-triage"), "production", "model-risk", "Marcus Feld", "approve", "ok", log=tmp_path / "a", write=False)


def test_bad_decision_is_refused(tmp_path, fresh):
    with pytest.raises(SignoffRefused):
        sign(
            fresh("halcyon-fraud-triage"), "production", "model-risk", "Marcus Feld", "maybe", "Not sure about this.", log=tmp_path / "a", write=False
        )


def test_refused_signoff_writes_nothing(tmp_path, fresh):
    log = tmp_path / "a"
    with pytest.raises(SignoffRefused):
        sign(
            fresh("halcyon-fraud-triage"), "production", "model-risk", "Fraud Data Science team", "approve", "Looks fine to us.", log=log, write=False
        )
    assert read_log(log) == []


def test_tampering_breaks_the_chain(tmp_path):
    log = tmp_path / "a"
    for i in range(3):
        append({"event": "x", "i": i}, log)
    lines = log.read_text().splitlines()
    lines[1] = lines[1].replace('"i":1', '"i":9')
    log.write_text("\n".join(lines) + "\n")
    v = verify_chain(log)
    assert not v["ok"] and v["broken_at"] == 2


def test_deleting_an_entry_breaks_the_chain(tmp_path):
    log = tmp_path / "a"
    for i in range(3):
        append({"event": "x", "i": i}, log)
    lines = log.read_text().splitlines()
    log.write_text(lines[0] + "\n" + lines[2] + "\n")
    assert not verify_chain(log)["ok"]


def test_rejection_does_not_count_as_approval(tmp_path, fresh, monkeypatch):
    rec = fresh("halcyon-fraud-triage")
    s = sign(
        rec, "retired", "model-risk", "Marcus Feld (Model Risk Management)", "reject", "Fallback not rehearsed yet.", log=tmp_path / "a", write=False
    )
    rec.approvals["signoffs"].append(s)
    assert "model-risk" not in valid_signoffs(rec, "retired")
