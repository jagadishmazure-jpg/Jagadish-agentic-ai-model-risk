"""Load the model inventory and each model's four pillar artifacts from registry/."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from modelrisk import REGISTRY

FILES = {
    "model_card": "model-card.yaml",
    "data_sheet": "data-sheet.yaml",
    "risk_cards": "risk-cards.yaml",
    "scenarios": "scenarios.yaml",
    "approvals": "approvals.yaml",
}
PILLARS = ("model_card", "data_sheet", "risk_cards", "scenarios")


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text())


@dataclass
class ModelRecord:
    id: str
    stage: str
    folder: Path
    model_card: dict[str, Any] | None
    data_sheet: dict[str, Any] | None
    risk_cards: dict[str, Any] | None
    scenarios: dict[str, Any] | None
    approvals: dict[str, Any] | None

    @property
    def kind(self) -> str:
        return (self.model_card or {}).get("kind", "domain")

    def missing_pillars(self) -> list[str]:
        return [p for p in PILLARS if getattr(self, p) is None]

    def risks(self) -> list[dict[str, Any]]:
        return (self.risk_cards or {}).get("risks", [])

    def scenario_list(self) -> list[dict[str, Any]]:
        return (self.scenarios or {}).get("scenarios", [])


def inventory(root: Path = REGISTRY) -> dict[str, Any]:
    return load_yaml(root / "inventory.yaml")


def load(model_id: str, root: Path = REGISTRY) -> ModelRecord:
    entry = next(m for m in inventory(root)["models"] if m["id"] == model_id)
    folder = root / entry["path"]
    docs = {k: (load_yaml(folder / f) if (folder / f).exists() else None) for k, f in FILES.items()}
    return ModelRecord(id=model_id, stage=entry["stage"], folder=folder, **docs)


def load_all(root: Path = REGISTRY) -> list[ModelRecord]:
    return [load(m["id"], root) for m in inventory(root)["models"]]
