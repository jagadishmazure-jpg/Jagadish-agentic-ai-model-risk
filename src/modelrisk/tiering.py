"""Inventory risk tiering and the EU AI Act class, computed from the model card.

Materiality points (0-12):
  decision impact     affects individuals +3, irreversible +1, financial exposure high +2 / medium +1
  autonomy            act +3, act-with-approval +1, suggest +0
  data sensitivity    phi or protected-attributes +2, pii or financial +1 (max 2)
  scale               monthly volume >= 100k +1
Tier 1 (high) >= 7, tier 2 (medium) 4-6, tier 3 (low) <= 3. A model card may only raise the
computed tier through ``regulatory.tier_floor`` (never lower it).

EU AI Act class comes from the use, not the score: credit scoring of natural persons and
life/health insurance pricing are high-risk uses; detecting financial fraud is carved out of the
credit-scoring use; customer-facing chat needs transparency; everything else is minimal.
"""

from __future__ import annotations

from typing import Any

HIGH_RISK_USES = {"creditworthiness", "life-health-insurance-pricing", "essential-services-eligibility", "employment"}
TRANSPARENCY_USES = {"customer-chat", "generated-content"}


def materiality(card: dict[str, Any]) -> dict[str, int]:
    d = card["decision_impact"]
    pts = {
        "affects_individuals": 3 if d["affects_individuals"] else 0,
        "irreversible": 0 if d["reversible"] else 1,
        "financial_exposure": {"high": 2, "medium": 1}.get(d["financial_exposure"], 0),
        "autonomy": {"act": 3, "act-with-approval": 1}.get(card["system"]["autonomy"], 0),
        "sensitivity": min(2, sum(2 if s in ("phi", "protected-attributes") else 1 if s in ("pii", "financial") else 0
                                  for s in card["data_sensitivity"])),
        "scale": 1 if card.get("monthly_volume", 0) >= 100_000 else 0,
    }
    return pts


def tier(card: dict[str, Any]) -> int:
    score = sum(materiality(card).values())
    computed = 1 if score >= 7 else 2 if score >= 4 else 3
    floor = card.get("regulatory", {}).get("tier_floor", 3)
    return min(computed, floor)


def eu_ai_act_class(card: dict[str, Any]) -> str:
    uses = set(card.get("regulatory", {}).get("eu_ai_act_uses", []))
    if uses & HIGH_RISK_USES:
        return "high-risk"
    if uses & TRANSPARENCY_USES:
        return "limited (transparency)"
    return "minimal"
