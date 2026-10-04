import pytest
import yaml

from modelrisk import REGULATORY, ROOT

DOC = yaml.safe_load((REGULATORY / "mapping.yaml").read_text())
ITEMS = [(f["id"], i["ref"], p) for f in DOC["frameworks"] for i in f["items"] for p in i["implemented_by"]]


def test_required_frameworks_are_mapped():
    ids = {f["id"] for f in DOC["frameworks"]}
    assert {"csa-ai-mrm", "nist-ai-rmf", "eu-ai-act", "sr-11-7", "iso-42001", "hipaa", "fair-lending"} <= ids


def test_nist_covers_all_four_functions():
    refs = [i["ref"] for f in DOC["frameworks"] if f["id"] == "nist-ai-rmf" for i in f["items"]]
    assert all(any(r.startswith(fn) for r in refs) for fn in ("GOVERN", "MAP", "MEASURE", "MANAGE"))


def test_eu_ai_act_tiers_are_described():
    eu = next(f for f in DOC["frameworks"] if f["id"] == "eu-ai-act")
    assert set(eu["tiers"]) == {"prohibited", "high-risk", "limited", "minimal"}


@pytest.mark.parametrize("fw,ref,path", ITEMS)
def test_mapped_implementation_exists(fw, ref, path):
    assert (ROOT / path).exists(), f"{fw} {ref}: {path}"


def test_every_item_has_an_evidence_command():
    assert all(i["evidence"].startswith("modelrisk ") for f in DOC["frameworks"] for i in f["items"])


def test_csa_attribution_links_the_working_group():
    csa = next(f for f in DOC["frameworks"] if f["id"] == "csa-ai-mrm")
    assert csa["source"] == "https://cloudsecurityalliance.org/research/working-groups/ai-technology-and-risk"


@pytest.mark.parametrize(
    "model_id,repo",
    [
        ("pfa-mortgage-flow", "Jagadish-azure-agent-platform"),
        ("pfs-safety-layer", "Jagadish-azure-ai-integration-platform"),
        ("pal-agent-labs", "Jagadish-azure-agent-labs"),
        ("pfb-fabric-data-agent", "Jagadish-fabric-enterprise-bi"),
        ("pff-finops-agent", "Jagadish-azure-finops"),
    ],
)
def test_portfolio_cards_govern_the_other_repos(records, model_id, repo):
    card = records[model_id].model_card
    assert card["kind"] == "portfolio" and f"/jagadishmazure-jpg/{repo}/" in card["governs"]
    assert records[model_id].risks() and all(c.get("evidence", repo).startswith(repo) for r in records[model_id].risks() for c in r["controls"])
