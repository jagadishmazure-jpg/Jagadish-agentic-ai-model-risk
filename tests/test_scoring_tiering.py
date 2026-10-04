import pytest

from modelrisk.scoring import band, combined_effectiveness, heatmap, score_risk, within_appetite
from modelrisk.tiering import eu_ai_act_class, materiality, tier


@pytest.mark.parametrize("score,name", [(1, "low"), (4, "low"), (5, "medium"), (9, "medium"), (10, "high"), (15, "high"), (16, "critical"), (25, "critical"), (0.4, "low")])
def test_bands(score, name):
    assert band(score) == name


def _ctl(eff, status="implemented"):
    return {"id": f"C{eff}", "effectiveness": eff, "status": status}


def test_combined_effectiveness_compounds():
    assert combined_effectiveness([_ctl(0.5), _ctl(0.5)]) == 0.75


def test_planned_controls_earn_no_credit():
    assert combined_effectiveness([_ctl(0.8, "planned")]) == 0.0


def test_overrides_replace_credited_effectiveness():
    assert combined_effectiveness([_ctl(0.8)], {"C0.8": 0.0}) == 0.0


def test_residual_is_inherent_times_remaining_exposure():
    r = {"id": "R", "title": "t", "category": "security", "owner": "o", "likelihood": 4, "impact": 5, "controls": [_ctl(0.75)]}
    s = score_risk(r)
    assert s["inherent"] == 20 and s["inherent_band"] == "critical" and s["residual"] == 5.0 and s["residual_band"] == "medium"


def test_appetite_by_tier():
    assert within_appetite("low", 1) and not within_appetite("medium", 1)
    assert within_appetite("medium", 2) and not within_appetite("high", 3)


def test_heatmap_places_risks_by_impact_and_likelihood():
    grid = heatmap([{"likelihood": 4, "impact": 5}, {"likelihood": 1, "impact": 1}])
    assert grid[0][3] == 1 and grid[4][0] == 1 and sum(map(sum, grid)) == 2


EXPECTED = {
    "halcyon-fraud-triage": (1, "minimal"), "bramblewood-claims-triage": (1, "minimal"),
    "cedarhollow-underwriting-assistant": (1, "high-risk"), "juniper-prior-auth": (1, "high-risk"),
    "marigold-pricing-demand": (2, "minimal"), "pfa-mortgage-flow": (1, "high-risk"), "pfs-safety-layer": (2, "minimal"),
    "pal-agent-labs": (3, "minimal"), "pfb-fabric-data-agent": (2, "minimal"), "pff-finops-agent": (3, "minimal"),
}


@pytest.mark.parametrize("model_id", sorted(EXPECTED))
def test_tier_and_eu_class(records, model_id):
    card = records[model_id].model_card
    assert (tier(card), eu_ai_act_class(card)) == EXPECTED[model_id]


def test_fraud_detection_is_carved_out_of_credit_scoring(records):
    assert eu_ai_act_class(records["halcyon-fraud-triage"].model_card) == "minimal"


def test_tier_floor_can_only_raise_the_tier(records):
    card = dict(records["pfb-fabric-data-agent"].model_card)
    assert sum(materiality(card).values()) <= 3 and tier(card) == 2
    card["regulatory"] = {**card["regulatory"], "tier_floor": 3}
    assert tier(card) == 3


def test_materiality_points(records):
    pts = materiality(records["halcyon-fraud-triage"].model_card)
    assert pts == {"affects_individuals": 3, "irreversible": 0, "financial_exposure": 2, "autonomy": 3, "sensitivity": 2, "scale": 1}


def test_transparency_class():
    card = {"regulatory": {"eu_ai_act_uses": ["customer-chat"]}}
    assert eu_ai_act_class(card) == "limited (transparency)"
