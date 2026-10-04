"""JSON Schema validation for every pillar artifact (draft 2020-12)."""

from __future__ import annotations

import json
from functools import cache
from typing import Any

from jsonschema import Draft202012Validator

from modelrisk import SCHEMAS

KINDS = ("model-card", "data-sheet", "risk-card", "scenario", "inventory", "approvals")


@cache
def validator(kind: str) -> Draft202012Validator:
    schema = json.loads((SCHEMAS / f"{kind}.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def errors(kind: str, doc: Any) -> list[str]:
    """Human-readable errors, empty when the document is valid."""
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in validator(kind).iter_errors(doc)]
