from pathlib import Path

import pytest

from modelrisk.mcp_supply import APPROVED, APPROVED_MANIFEST, Pin, ServerDecl, check_manifest, check_server, demo


def test_patched_versions_are_the_reviewed_pins():
    assert APPROVED["mcp-server-git"] == Pin("calver", (2026, 11, 18), "pypi")
    assert APPROVED["@modelcontextprotocol/server-filesystem"] == Pin("semver", (2, 4, 0), "npm")
    assert APPROVED["@modelcontextprotocol/server-everything"] == Pin("semver", (2, 3, 1), "npm")


def test_approved_manifest_passes():
    result = check_manifest(APPROVED_MANIFEST)
    assert result["ok"]
    assert {item.name for item in result["findings"]} == set(APPROVED)


@pytest.mark.parametrize(
    ("name", "version", "registry", "reason"),
    [
        ("mcp-server-git", "2026.11.11", "pypi", "below the patched pin"),
        ("@modelcontextprotocol/server-filesystem", "2.3.9", "npm", "below the patched pin"),
        ("@modelcontextprotocol/server-everything", "2.3.0", "npm", "below the patched pin"),
        ("@modelcontextprotocol/server-filesystem", "2.4.1", "npm", "not the reviewed pin"),
        ("mcp-server-git", "2026.12.1", "pypi", "not the reviewed pin"),
        ("@modelcontextprotocol/server-filesystem", "2026.8.31", "npm", "version scheme is not the pinned scheme"),
        ("mcp-server-git", "2.4.0", "pypi", "version scheme is not the pinned scheme"),
        ("@modelcontextprotocol/server-filesystem", "^2.4.0", "npm", "version is not an exact pin"),
        ("@modelcontextprotocol/server-filesystem", "latest", "npm", "version is not an exact pin"),
        ("@modelcontextprotocol/server-filesystem", "v2.4.0", "npm", "version is not an exact pin"),
        ("@modelcontextprotocol/server-filesystem", "2.4", "npm", "version width does not match the pin"),
        ("mcp-server-git", "2026.11.18", "npm", "registry is not approved"),
        ("mcp-server-fetch", "2026.11.18", "pypi", "not on the allowlist"),
        ("mcp-server-shell", "1.0.0", "pypi", "not on the allowlist"),
        ("MCP-server-git", "2026.11.18", "pypi", "not on the allowlist"),
    ],
)
def test_unapproved_servers_are_rejected(name, version, registry, reason):
    found = check_server(ServerDecl(name, version, registry))
    assert not found.ok and found.reason == reason


def test_date_version_does_not_satisfy_a_semantic_pin():
    found = check_server(ServerDecl("@modelcontextprotocol/server-filesystem", "2026.8.31", "npm"))
    assert found.reason == "version scheme is not the pinned scheme"


def test_below_the_patched_pin_is_rejected():
    assert not check_server(ServerDecl("mcp-server-git", "2026.11.11", "pypi")).ok
    assert not check_server(ServerDecl("@modelcontextprotocol/server-filesystem", "2.3.9", "npm")).ok


def test_published_package_off_the_allowlist_is_rejected():
    found = check_server(ServerDecl("mcp-server-fetch", "2026.11.18", "pypi"))
    assert found.reason == "not on the allowlist"


def test_empty_manifest_fails():
    assert check_manifest(())["ok"] is False


def test_demo_passes_the_reviewed_manifest_and_fails_the_fixtures():
    result = demo()
    assert result["approved_ok"] is True
    assert result["rejected_ok"] is False
    assert all(row["result"] == "FAIL" for row in result["rejected"])


def test_supply_module_stays_defensive():
    text = Path(check_server.__code__.co_filename).read_text().lower()
    for word in ("exploit", "payload", "proof of concept", "socket", "urllib", "httpx"):
        assert word not in text
