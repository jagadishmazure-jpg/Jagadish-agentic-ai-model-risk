"""Deny-by-default network policy for one sandboxed agent session.

A sandbox stops code the agent wrote from running on the worker. It does not
stop the agent using a destination it was allowed to reach. Treat the session
as an insider: nothing is reachable unless a rule allows it, an explicit deny
beats a broader allow, and every decision is appended to a hash-chained log.

This is an offline stand-in for a policy enforced next to the sandbox. It does
not connect anywhere. Hosted behaviour of that pattern is not executed here.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from modelrisk.report import table

GENESIS = "0" * 64


class PolicyError(Exception):
    pass


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class Rule:
    id: str
    effect: str
    scheme: str
    host: str
    path_prefix: str = "/"
    note: str = ""

    def __post_init__(self) -> None:
        if self.effect not in {"allow", "deny"}:
            raise PolicyError(f"{self.id}: effect must be allow or deny")
        if not self.scheme or self.scheme != self.scheme.lower():
            raise PolicyError(f"{self.id}: scheme must be lowercase")
        if self.host != self.host.lower() or not self.host:
            raise PolicyError(f"{self.id}: host must be a lowercase pattern")
        if self.host.startswith("*") and self.host != "*" and not (self.host.startswith("*.") and "." in self.host[2:]):
            raise PolicyError(f"{self.id}: host wildcard must be * or *.suffix")
        if not self.path_prefix.startswith("/"):
            raise PolicyError(f"{self.id}: path prefix must start with /")


@dataclass(frozen=True)
class Resource:
    scheme: str
    host: str
    path: str = "/"

    def canonical(self) -> str:
        return f"{self.scheme}://{self.host}{self.path}"


def parse_resource(url: str) -> Resource:
    """Fail closed on anything that is not ``scheme://host/path``."""
    if url.count("://") != 1:
        raise PolicyError("resource needs one scheme")
    scheme, rest = url.split("://", 1)
    if not scheme or any(c in url for c in ("@", "?", "#", " ", "\\")):
        raise PolicyError("resource is not a plain scheme, host and path")
    host, _, path = rest.partition("/")
    if not host or ":" in host or host.startswith("."):
        raise PolicyError("host must be a bare name")
    return Resource(scheme.lower(), host.lower(), "/" + path)


def _host_matches(pattern: str, host: str) -> bool:
    if pattern == "*":
        return True
    if pattern.startswith("*."):
        suffix = pattern[1:]
        return host.endswith(suffix) and len(host) > len(suffix)
    return host == pattern


def _path_matches(prefix: str, path: str) -> bool:
    if prefix == "/":
        return True
    base = prefix.rstrip("/")
    return path == base or path.startswith(base + "/")


def rule_matches(rule: Rule, resource: Resource) -> bool:
    if rule.scheme != "*" and rule.scheme != resource.scheme:
        return False
    return _host_matches(rule.host, resource.host) and _path_matches(rule.path_prefix, resource.path)


def _pick(rules: list[Rule]) -> Rule:
    """Most specific host, then the longest path, then a stable id."""

    def rank(rule: Rule) -> tuple[int, int, str]:
        if rule.host == "*":
            host_rank = 0
        elif rule.host.startswith("*."):
            host_rank = 1
        else:
            host_rank = 2
        return (-host_rank, -len(rule.path_prefix), rule.id)

    return min(rules, key=rank)


def evaluate(rules: tuple[Rule, ...] | list[Rule], resource: Resource) -> tuple[str, str, str]:
    """Return ``(effect, rule id, reason)``. No matching allow is a deny."""
    matched = [rule for rule in rules if rule_matches(rule, resource)]
    denies = [rule for rule in matched if rule.effect == "deny"]
    if denies:
        rule = _pick(denies)
        return "deny", rule.id, "explicit deny"
    allows = [rule for rule in matched if rule.effect == "allow"]
    if allows:
        return "allow", _pick(allows).id, "matched allow"
    return "deny", "default-deny", "deny by default"


@dataclass
class AuditLog:
    entries: list[dict[str, Any]] = field(default_factory=list)
    _prev: str = GENESIS

    def record(self, **fields: Any) -> dict[str, Any]:
        entry = {"seq": len(self.entries) + 1, **fields, "prev": self._prev}
        entry["hash"] = hashlib.sha256((self._prev + _canonical(entry)).encode()).hexdigest()
        self.entries.append(entry)
        self._prev = entry["hash"]
        return entry

    def verify(self) -> dict[str, Any]:
        prev = GENESIS
        for i, entry in enumerate(self.entries, 1):
            body = {k: v for k, v in entry.items() if k != "hash"}
            if entry.get("prev") != prev or entry.get("seq") != i:
                return {"ok": False, "broken_at": i, "reason": "sequence or previous-hash mismatch"}
            digest = hashlib.sha256((prev + _canonical(body)).encode()).hexdigest()
            if digest != entry.get("hash"):
                return {"ok": False, "broken_at": i, "reason": "entry hash mismatch"}
            prev = entry["hash"]
        return {"ok": True, "entries": len(self.entries)}


@dataclass(frozen=True)
class Session:
    """A session holds a fixed rule tuple. It has no method that adds a grant."""

    session_id: str
    model_id: str
    rules: tuple[Rule, ...]
    audit: AuditLog

    def reach(self, resource: Resource) -> dict[str, Any]:
        effect, rule_id, reason = evaluate(self.rules, resource)
        return self.audit.record(
            session_id=self.session_id,
            model_id=self.model_id,
            resource=resource.canonical(),
            effect=effect,
            rule_id=rule_id,
            reason=reason,
        )


# Internal estate the session was granted, with insider routes carved out.
# A broad allow is the access the agent was given; explicit denies are the
# misuse of that access. Anything else, including the public internet, falls
# through to deny.
ENTERPRISE_RULES: tuple[Rule, ...] = (
    Rule("allow-internal", "allow", "https", "*.corp.internal", "/", "internal estate granted to the session"),
    Rule("allow-model", "allow", "https", "models.corp.internal", "/foundry", "scoring route only"),
    Rule("deny-model-admin", "deny", "https", "models.corp.internal", "/admin", "admin plane is not an agent route"),
    Rule("deny-payroll", "deny", "https", "payroll.corp.internal", "/", "payroll is not an agent task"),
    Rule("deny-wire", "deny", "https", "wires.corp.internal", "/", "payments stay with people"),
    Rule("allow-register", "allow", "mcp", "register.corp.internal", "/", "read-only risk register"),
)


DEMO_REACHES: tuple[str, ...] = (
    "https://models.corp.internal/foundry/score",
    "https://evidence.corp.internal/packs/ex-1",
    "https://models.corp.internal/admin/keys",
    "https://payroll.corp.internal/export",
    "https://wires.corp.internal/submit",
    "https://evil.example/collect",
    "mcp://register.corp.internal/tools/query_risks",
    "mcp://unknown.example/exec",
)


def open_session(session_id: str, model_id: str, rules: Iterable[Rule] | None = None) -> Session:
    chosen = ENTERPRISE_RULES if rules is None else tuple(rules)
    return Session(session_id, model_id, chosen, AuditLog())


def demo() -> dict[str, Any]:
    session = open_session("ses-grid", "halcyon-fraud-triage")
    decisions = [session.reach(parse_resource(url)) for url in DEMO_REACHES]
    verified = session.audit.verify()
    public = [{"resource": d["resource"], "effect": d["effect"], "rule_id": d["rule_id"], "reason": d["reason"]} for d in decisions]
    return {
        "session_id": session.session_id,
        "model_id": session.model_id,
        "default": "deny",
        "audit_ok": verified["ok"],
        "audit_entries": verified["entries"],
        "allows": sum(row["effect"] == "allow" for row in public),
        "denies": sum(row["effect"] == "deny" for row in public),
        "decisions": public,
    }


def render_demo(result: dict[str, Any] | None = None) -> str:
    result = demo() if result is None else result
    chain = "ok" if result["audit_ok"] else "FAIL"
    lines = [
        "framing: agents are insider risks; the sandbox is not the policy",
        f"session {result['session_id']} model {result['model_id']}",
        "default: deny",
        f"audit chain: {chain} ({result['audit_entries']})",
        table(result["decisions"], ["resource", "effect", "rule_id", "reason"], ["resource", "effect", "rule", "reason"]),
        f"allows: {result['allows']}  denies: {result['denies']}",
    ]
    return "\n".join(lines)
