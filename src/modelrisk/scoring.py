"""Likelihood x impact scoring, control effectiveness and residual risk.

    inherent  = likelihood x impact                       (1..25)
    combined  = 1 - product(1 - effectiveness)            over IMPLEMENTED controls only
    residual  = inherent x (1 - combined)

Planned controls earn no credit. Effectiveness is capped at 0.9 by the schema, so residual risk
never reaches zero on paper. Scenario evidence can lower a control's credited effectiveness
(see ``combine.update_residuals``).
"""

from __future__ import annotations

from typing import Any

BANDS = [(16, "critical"), (10, "high"), (5, "medium"), (1, "low")]

# Highest residual band each inventory tier may carry without a documented risk acceptance.
APPETITE = {1: "low", 2: "medium", 3: "medium"}
BAND_ORDER = ["low", "medium", "high", "critical"]


def band(score: float) -> str:
    for floor, name in BANDS:
        if score >= floor:
            return name
    return "low"


def combined_effectiveness(controls: list[dict[str, Any]], overrides: dict[str, float] | None = None) -> float:
    overrides = overrides or {}
    remaining = 1.0
    for c in controls:
        if c.get("status") != "implemented":
            continue
        remaining *= 1 - overrides.get(c["id"], c["effectiveness"])
    return round(1 - remaining, 4)


def score_risk(risk: dict[str, Any], overrides: dict[str, float] | None = None) -> dict[str, Any]:
    inherent = risk["likelihood"] * risk["impact"]
    eff = combined_effectiveness(risk["controls"], overrides)
    residual = round(inherent * (1 - eff), 2)
    return {
        "id": risk["id"], "title": risk["title"], "category": risk["category"], "owner": risk["owner"],
        "likelihood": risk["likelihood"], "impact": risk["impact"],
        "inherent": inherent, "inherent_band": band(inherent),
        "control_effectiveness": eff, "residual": residual, "residual_band": band(residual),
        "implemented_controls": sum(c["status"] == "implemented" for c in risk["controls"]),
    }


def within_appetite(residual_band: str, tier: int) -> bool:
    return BAND_ORDER.index(residual_band) <= BAND_ORDER.index(APPETITE[tier])


def heatmap(scored: list[dict[str, Any]], key: str = "inherent") -> list[list[int]]:
    """5x5 counts, rows = impact 5..1, columns = likelihood 1..5 (residual uses rounded L x I share)."""
    grid = [[0] * 5 for _ in range(5)]
    for r in scored:
        grid[5 - r["impact"]][r["likelihood"] - 1] += 1
    return grid
