import hashlib
import json
from pathlib import Path

from modelrisk import ROOT
from modelrisk.examiner import CONTROL_MODULES, build_pack, framework_rows, render_pack


def _body(pack):
    return {k: v for k, v in pack.items() if k != "digest"}


def test_examiner_pack_records_no_duplicate_model_calls():
    pack = build_pack()
    cache = pack["context_cache"]
    assert cache["duplicate_model_calls"] == 0
    assert cache["calls"] == {"worker-a": 1, "worker-b": 2}
    assert cache["reused_saved_output"] is True


def test_examiner_pack_maps_onto_the_framework():
    rows = framework_rows()
    refs = {(row["framework"], row["ref"]) for row in rows}
    assert ("nist-ai-rmf", "GOVERN 6.1") in refs
    assert ("nist-ai-rmf", "MAP 4.1") in refs
    assert ("nist-ai-rmf", "MANAGE 2.4") in refs
    assert ("eu-ai-act", "Art. 12") in refs
    assert ("eu-ai-act", "Art. 15") in refs
    assert ("sr-11-7", "vendor products") in refs
    assert ("iso-42001", "Annex A.10") in refs
    assert ("csa-ai-mrm", "examined controls") in refs
    assert all(any(path in CONTROL_MODULES for path in row["implemented_by"]) for row in rows)


def test_pack_digest_is_stable_and_covers_the_body():
    first, second = build_pack(), build_pack()
    assert first["digest"] == second["digest"]
    body = json.dumps(_body(first), sort_keys=True, separators=(",", ":"))
    assert first["digest"] == hashlib.sha256(body.encode()).hexdigest()
    assert "duplicate model calls: 0" in render_pack(first)
    assert first["digest"] in render_pack(first)


def test_pack_network_and_supply_results():
    pack = build_pack()
    assert pack["network"]["audit_ok"] and pack["network"]["denies"] > pack["network"]["allows"]
    assert pack["mcp_supply"]["approved_ok"] is True
    assert pack["mcp_supply"]["rejected_ok"] is False
    assert pack["posture"] == "offline synthetic; no live cloud calls"


def test_readme_cites_sources_and_marks_preview_claims():
    text = (ROOT / "README.md").read_text()
    assert "https://www.techtarget.com/news/microsofts-azure-upgrades-add-speed-and-security-to-agents/875110/" in text
    assert "https://github.com/modelcontextprotocol/servers/releases/tag/v2.5.0" in text
    assert "[verify]" in text
    assert "2026.11.18" in text and "2.4.0" in text
    for name in ("network-policy.md", "context-cache.md", "mcp-supply-chain.md"):
        assert "[verify]" in (ROOT / "docs" / "components" / name).read_text()


def test_control_modules_do_not_call_the_network():
    for path in CONTROL_MODULES:
        text = Path(ROOT / path).read_text()
        for word in ("socket", "urllib", "httpx", "requests"):
            assert word not in text, path
