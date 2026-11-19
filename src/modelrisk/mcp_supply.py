"""Allowlist and exact version pin for MCP servers a session may call.

A declared server is admitted only when its name is on the allowlist, its
registry matches, and its version is an exact pin equal to the reviewed
version. The reviewed versions are the patched releases from the reference
server release v2.5.0: ``mcp-server-git`` 2026.11.18,
``@modelcontextprotocol/server-filesystem`` 2.4.0 and
``@modelcontextprotocol/server-everything`` 2.3.1. Older versions are below
that fix. Newer versions are not admitted until someone reviews them and adds
the pin. Ranges, floating tags and a date-style version on a semantic pin are
rejected.

Being published is not the same as being approved: packages from that release
that this allowlist does not name are rejected.

This module does not contact a registry and does not describe how an
unpatched server fails.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from modelrisk.report import table


@dataclass(frozen=True)
class Pin:
    scheme: str
    version: tuple[int, ...]
    registry: str


@dataclass(frozen=True)
class ServerDecl:
    name: str
    version: str
    registry: str


@dataclass(frozen=True)
class Finding:
    name: str
    version: str
    registry: str
    ok: bool
    reason: str


# Exact reviewed pins. A newer release stays out until it is added here.
APPROVED: dict[str, Pin] = {
    "mcp-server-git": Pin("calver", (2026, 11, 18), "pypi"),
    "@modelcontextprotocol/server-filesystem": Pin("semver", (2, 4, 0), "npm"),
    "@modelcontextprotocol/server-everything": Pin("semver", (2, 3, 1), "npm"),
}

APPROVED_MANIFEST: tuple[ServerDecl, ...] = tuple(
    ServerDecl(name, ".".join(str(part) for part in pin.version), pin.registry) for name, pin in APPROVED.items()
)

REJECTED_FIXTURES: tuple[ServerDecl, ...] = (
    ServerDecl("mcp-server-git", "2026.11.11", "pypi"),
    ServerDecl("@modelcontextprotocol/server-filesystem", "2026.8.31", "npm"),
    ServerDecl("@modelcontextprotocol/server-filesystem", "^2.4.0", "npm"),
    ServerDecl("mcp-server-fetch", "2026.11.18", "pypi"),
    ServerDecl("mcp-server-git", "2026.11.18", "npm"),
)


def parse_exact_pin(version: str) -> tuple[str, tuple[int, ...]] | None:
    """An exact pin is digits and dots only. Ranges and tags are not pins."""
    if not version or version != version.strip():
        return None
    if any(char in version for char in "*^~><=vV \t"):
        return None
    parts = version.split(".")
    if len(parts) < 2 or not all(part.isdigit() and part == str(int(part)) for part in parts):
        return None
    nums = tuple(int(part) for part in parts)
    if len(nums) == 3 and nums[0] >= 2000:
        return "calver", nums
    return "semver", nums


def check_server(server: ServerDecl) -> Finding:
    pin = APPROVED.get(server.name)
    if pin is None:
        return Finding(server.name, server.version, server.registry, False, "not on the allowlist")
    if server.registry != pin.registry:
        return Finding(server.name, server.version, server.registry, False, "registry is not approved")
    parsed = parse_exact_pin(server.version)
    if parsed is None:
        return Finding(server.name, server.version, server.registry, False, "version is not an exact pin")
    scheme, nums = parsed
    if scheme != pin.scheme:
        return Finding(server.name, server.version, server.registry, False, "version scheme is not the pinned scheme")
    if len(nums) != len(pin.version):
        return Finding(server.name, server.version, server.registry, False, "version width does not match the pin")
    if nums < pin.version:
        return Finding(server.name, server.version, server.registry, False, "below the patched pin")
    if nums > pin.version:
        return Finding(server.name, server.version, server.registry, False, "not the reviewed pin")
    return Finding(server.name, server.version, server.registry, True, "pinned")


def check_manifest(servers: list[ServerDecl] | tuple[ServerDecl, ...]) -> dict[str, Any]:
    findings = [check_server(server) for server in servers]
    return {"ok": bool(findings) and all(item.ok for item in findings), "findings": findings}


def _public(finding: Finding) -> dict[str, Any]:
    return {
        "name": finding.name,
        "version": finding.version,
        "registry": finding.registry,
        "result": "ok" if finding.ok else "FAIL",
        "reason": finding.reason,
    }


def demo() -> dict[str, Any]:
    approved = check_manifest(APPROVED_MANIFEST)
    rejected = check_manifest(REJECTED_FIXTURES)
    return {
        "approved_ok": approved["ok"],
        "approved": [_public(item) for item in approved["findings"]],
        "rejected_ok": rejected["ok"],
        "rejected": [_public(item) for item in rejected["findings"]],
    }


def render_demo(result: dict[str, Any] | None = None) -> str:
    result = demo() if result is None else result
    cols = ["name", "version", "registry", "result", "reason"]
    approved = "PASS" if result["approved_ok"] else "FAIL"
    rejected = "PASS" if result["rejected_ok"] else "FAIL"
    return "\n".join(
        [
            f"approved manifest: {approved}",
            table(result["approved"], cols),
            f"rejected fixtures (not installed): {rejected}",
            table(result["rejected"], cols),
        ]
    )
