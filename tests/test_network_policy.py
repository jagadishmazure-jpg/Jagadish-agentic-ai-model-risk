import pytest

from modelrisk.network_policy import (
    ENTERPRISE_RULES,
    PolicyError,
    Rule,
    demo,
    evaluate,
    open_session,
    parse_resource,
    render_demo,
)


def _effect(url: str, rules=None):
    session = open_session("ses-test", "halcyon-fraud-triage", rules)
    return session.reach(parse_resource(url))


def test_public_internet_is_denied_by_default():
    decision = _effect("https://evil.example/collect")
    assert decision["effect"] == "deny" and decision["rule_id"] == "default-deny"


def test_explicit_deny_beats_a_broader_allow():
    payroll = _effect("https://payroll.corp.internal/export")
    wires = _effect("https://wires.corp.internal/submit")
    assert payroll["effect"] == "deny" and payroll["rule_id"] == "deny-payroll" and payroll["reason"] == "explicit deny"
    assert wires["rule_id"] == "deny-wire"


def test_model_admin_route_is_denied_on_the_same_host():
    score = _effect("https://models.corp.internal/foundry/score")
    admin = _effect("https://models.corp.internal/admin/keys")
    assert score["effect"] == "allow" and score["rule_id"] == "allow-model"
    assert admin["effect"] == "deny" and admin["rule_id"] == "deny-model-admin"


def test_granted_internal_and_register_routes_are_allowed():
    evidence = _effect("https://evidence.corp.internal/packs/ex-1")
    register = _effect("mcp://register.corp.internal/tools/query_risks")
    assert evidence["rule_id"] == "allow-internal"
    assert register["effect"] == "allow" and register["rule_id"] == "allow-register"


def test_empty_policy_denies_everything():
    decision = _effect("https://models.corp.internal/foundry/score", rules=[])
    assert decision["effect"] == "deny" and decision["rule_id"] == "default-deny"


def test_suffix_does_not_match_the_apex_or_a_lookalike():
    rules = [Rule("allow-internal", "allow", "https", "*.corp.internal")]
    for host in ("https://corp.internal/a", "https://notcorp.internal/a", "https://corp.internal.attacker.com/a"):
        assert evaluate(rules, parse_resource(host))[0] == "deny", host
    assert evaluate(rules, parse_resource("https://api.corp.internal/a"))[0] == "allow"


def test_path_prefix_does_not_match_a_sibling():
    rules = [Rule("allow-foundry", "allow", "https", "models.corp.internal", "/foundry")]
    assert evaluate(rules, parse_resource("https://models.corp.internal/foundry"))[0] == "allow"
    assert evaluate(rules, parse_resource("https://models.corp.internal/foundry/score"))[0] == "allow"
    assert evaluate(rules, parse_resource("https://models.corp.internal/foundry-admin"))[0] == "deny"


@pytest.mark.parametrize(
    "url",
    [
        "https://user@models.corp.internal/foundry",
        "https://models.corp.internal:443/foundry",
        "https://models.corp.internal/foundry?x=1",
        "https://models.corp.internal/foundry#frag",
        "models.corp.internal/foundry",
        "https:///foundry",
    ],
)
def test_odd_resources_fail_closed(url):
    with pytest.raises(PolicyError):
        parse_resource(url)


def test_caller_cannot_widen_the_policy_after_the_session_opens():
    rules = list(ENTERPRISE_RULES)
    session = open_session("ses-grid", "halcyon-fraud-triage", rules)
    rules.append(Rule("allow-world", "allow", "https", "*"))
    decision = session.reach(parse_resource("https://evil.example/collect"))
    assert decision["effect"] == "deny"
    with pytest.raises(AttributeError):
        session.rules = ()


def test_a_session_has_no_grant_method():
    session = open_session("ses-grid", "halcyon-fraud-triage")
    assert not any(hasattr(session, name) for name in ("allow", "grant", "add_rule"))


def test_tampering_breaks_the_network_audit_chain():
    session = open_session("ses-grid", "halcyon-fraud-triage")
    session.reach(parse_resource("https://evil.example/collect"))
    session.reach(parse_resource("https://models.corp.internal/foundry/score"))
    assert session.audit.verify()["ok"]
    session.audit.entries[0]["effect"] = "allow"
    assert session.audit.verify() == {"ok": False, "broken_at": 1, "reason": "entry hash mismatch"}


def test_deleting_an_entry_breaks_the_network_audit_chain():
    session = open_session("ses-grid", "halcyon-fraud-triage")
    session.reach(parse_resource("https://evil.example/collect"))
    session.reach(parse_resource("https://models.corp.internal/foundry/score"))
    session.audit.entries.pop(0)
    assert session.audit.verify()["ok"] is False


def test_demo_is_deny_by_default_and_the_chain_verifies():
    result = demo()
    assert result["default"] == "deny" and result["audit_ok"] and result["audit_entries"] == 8
    assert result["allows"] == 3 and result["denies"] == 5
    assert "agents are insider risks" in render_demo(result)


def test_bad_rule_is_rejected_at_construction():
    with pytest.raises(PolicyError):
        Rule("nope", "permit", "https", "models.corp.internal")
    with pytest.raises(PolicyError):
        Rule("wild", "allow", "https", "*evil.example")


def test_policy_module_does_not_open_sockets():
    from pathlib import Path

    import modelrisk.network_policy as policy

    text = Path(policy.__file__).read_text()
    for word in ("socket", "urllib", "httpx", "requests"):
        assert word not in text
