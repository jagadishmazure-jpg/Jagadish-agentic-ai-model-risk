"""Synthetic examiner pack for the sandbox controls.

The pack replays the network policy, the context cache and the MCP pin check,
then lists every item in ``regulatory/mapping.yaml`` that those modules
implement. The digest is the hash of that body. Nothing here is an attestation,
and nothing is sent to a cloud.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import yaml

from modelrisk import REGULATORY
from modelrisk.context_cache import demo as cache_demo
from modelrisk.context_cache import render_demo as render_cache
from modelrisk.mcp_supply import demo as supply_demo
from modelrisk.mcp_supply import render_demo as render_supply
from modelrisk.network_policy import demo as network_demo
from modelrisk.network_policy import render_demo as render_network
from modelrisk.report import table

CONTROL_MODULES = (
    "src/modelrisk/network_policy.py",
    "src/modelrisk/context_cache.py",
    "src/modelrisk/mcp_supply.py",
    "src/modelrisk/examiner.py",
)


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def framework_rows() -> list[dict[str, Any]]:
    doc = yaml.safe_load((REGULATORY / "mapping.yaml").read_text())
    rows = []
    for framework in doc["frameworks"]:
        for item in framework["items"]:
            hit = [path for path in item["implemented_by"] if path in CONTROL_MODULES]
            if not hit:
                continue
            rows.append(
                {
                    "framework": framework["id"],
                    "ref": item["ref"],
                    "evidence": item["evidence"],
                    "implemented_by": hit,
                }
            )
    rows.sort(key=lambda row: (str(row["framework"]), _ref_sort(row["ref"])))
    return rows


def _ref_sort(ref: object) -> tuple:
    """GOVERN, MAP, MEASURE, MANAGE, then article number, then the text."""
    text = str(ref)
    for index, prefix in enumerate(("GOVERN", "MAP", "MEASURE", "MANAGE")):
        if text.startswith(prefix):
            return (index, text)
    if text.startswith("Art."):
        tail = text.removeprefix("Art.").strip()
        return (4, int(tail) if tail.isdigit() else 0, text)
    return (5, text)


def build_pack() -> dict[str, Any]:
    body = {
        "pack_id": "EX-SYNTHETIC",
        "posture": "offline synthetic; no live cloud calls",
        "network": network_demo(),
        "context_cache": cache_demo(),
        "mcp_supply": supply_demo(),
        "framework": framework_rows(),
    }
    return {**body, "digest": hashlib.sha256(_canonical(body).encode()).hexdigest()}


def render_pack(pack: dict[str, Any] | None = None) -> str:
    pack = build_pack() if pack is None else pack
    mapped = [{"framework": row["framework"], "ref": row["ref"], "evidence": row["evidence"]} for row in pack["framework"]]
    return "\n".join(
        [
            f"pack {pack['pack_id']}",
            f"posture: {pack['posture']}",
            f"digest: {pack['digest']}",
            "",
            "1. network policy",
            render_network(pack["network"]),
            "",
            "2. context cache",
            render_cache(pack["context_cache"]),
            "",
            "3. mcp supply",
            render_supply(pack["mcp_supply"]),
            "",
            "4. framework map",
            table(mapped, ["framework", "ref", "evidence"]),
        ]
    )
