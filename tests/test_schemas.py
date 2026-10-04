import copy

import pytest

from modelrisk.registry import inventory
from modelrisk.schema import KINDS, errors, validator
from tests.conftest import ALL_IDS

ARTIFACTS = [("model_card", "model-card"), ("data_sheet", "data-sheet"), ("risk_cards", "risk-card"),
             ("scenarios", "scenario"), ("approvals", "approvals")]


@pytest.mark.parametrize("kind", KINDS)
def test_schemas_are_valid_draft_2020_12(kind):
    assert validator(kind).schema["$schema"].endswith("2020-12/schema")


@pytest.mark.parametrize("model_id", ALL_IDS)
@pytest.mark.parametrize("attr,kind", ARTIFACTS)
def test_every_artifact_validates(records, model_id, attr, kind):
    doc = getattr(records[model_id], attr)
    assert doc is not None, f"{model_id} is missing {attr}"
    assert errors(kind, doc) == []


def test_inventory_validates():
    assert errors("inventory", inventory()) == []


def test_unknown_fields_are_rejected(records):
    card = copy.deepcopy(records["halcyon-fraud-triage"].model_card)
    card["surprise"] = 1
    assert any("surprise" in e for e in errors("model-card", card))


def test_likelihood_must_be_one_to_five(records):
    rc = copy.deepcopy(records["halcyon-fraud-triage"].risk_cards)
    rc["risks"][0]["likelihood"] = 7
    assert errors("risk-card", rc)


def test_control_effectiveness_is_capped(records):
    rc = copy.deepcopy(records["halcyon-fraud-triage"].risk_cards)
    rc["risks"][0]["controls"][0]["effectiveness"] = 1.0
    assert errors("risk-card", rc)


def test_scenario_kind_is_constrained(records):
    sc = copy.deepcopy(records["halcyon-fraud-triage"].scenarios)
    sc["scenarios"][0]["kind"] = "vibes"
    assert errors("scenario", sc)


def test_signoff_digest_must_be_sha256(records):
    ap = copy.deepcopy(records["halcyon-fraud-triage"].approvals)
    ap["signoffs"][0]["digest"] = "abc"
    assert errors("approvals", ap)


def test_risk_categories_cover_the_nine_families():
    cats = validator("risk-card").schema["properties"]["risks"]["items"]["properties"]["category"]["enum"]
    assert len(cats) == 9 and "supply-chain" in cats and "environmental" in cats
