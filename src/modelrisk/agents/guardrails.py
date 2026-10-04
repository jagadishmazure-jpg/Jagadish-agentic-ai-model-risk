"""Guardrails shared by the five agents.

* ``screen``: untrusted text (memos, documents, notes) is scanned for instruction-like content.
  Flagged text is quoted as data and never acted on.
* ``mask``: PII and PHI patterns are replaced before text leaves the agent (outputs, logs).
* ``ToolPolicy``: per-agent tool allow-list, approval-required tools and argument limits.
* ``Budget``: token and model-call caps per task; the graph's step cap is the loop guard.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) (instructions|rules)",
    r"disregard (the |your )?(policy|rules|instructions)",
    r"you are now",
    r"\bsystem prompt\b",
    r"(approve|release|mark) (this|it|the claim|the transaction|the request) (immediately|now|as safe|without review)",
    r"call (the )?tool",
    r"set (the )?price to",
]
_INJ = re.compile("|".join(INJECTION_PATTERNS), re.I)

MASKS = {
    "ssn": (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    "card": (re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"), "[CARD]"),
    "email": (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "[EMAIL]"),
    "phone": (re.compile(r"\b\d{3}[-.]\d{3}[-.]\d{4}\b"), "[PHONE]"),
    "mrn": (re.compile(r"\bMRN[- ]?\d{6,}\b", re.I), "[MRN]"),
    "member": (re.compile(r"\bMBR[- ]?\d{6,}\b", re.I), "[MEMBER-ID]"),
    "dob": (re.compile(r"\b(?:DOB|born)[: ]+\d{1,2}/\d{1,2}/\d{4}\b", re.I), "[DOB]"),
    "account": (re.compile(r"\bACCT[- ]?\d{8,}\b", re.I), "[ACCOUNT]"),
}
PII_KINDS = ("ssn", "card", "email", "phone", "account")
PHI_KINDS = (*PII_KINDS, "mrn", "member", "dob")


def screen(text: str) -> dict[str, Any]:
    """Return {'flagged': bool, 'matches': [...]} for untrusted text."""
    hits = [m.group(0) for m in _INJ.finditer(text or "")]
    return {"flagged": bool(hits), "matches": hits}


def mask(text: str, kinds: tuple[str, ...] = PII_KINDS) -> str:
    for k in kinds:
        rx, token = MASKS[k]
        text = rx.sub(token, text)
    return text


def find_sensitive(text: str, kinds: tuple[str, ...] = PHI_KINDS) -> list[str]:
    """Which sensitive patterns are still present (used by the PII-leak scenario)."""
    return [k for k in kinds if MASKS[k][0].search(text or "")]


class ToolDenied(Exception):
    pass


@dataclass
class ToolPolicy:
    allowed: set[str]
    needs_approval: set[str] = field(default_factory=set)
    limits: dict[str, dict[str, float]] = field(default_factory=dict)  # tool -> {arg: max}
    enforce: bool = True
    log: list[dict[str, Any]] = field(default_factory=list)

    def call(self, tool: str, approved: bool = False, **args: Any) -> dict[str, Any]:
        entry = {"tool": tool, "args": args, "approved": approved, "executed": False, "reason": ""}
        self.log.append(entry)
        if self.enforce:
            if tool not in self.allowed:
                entry["reason"] = "not on the allow-list"
                raise ToolDenied(f"{tool}: not on the allow-list")
            if tool in self.needs_approval and not approved:
                entry["reason"] = "needs human approval"
                raise ToolDenied(f"{tool}: needs human approval")
            for arg, cap in self.limits.get(tool, {}).items():
                if abs(float(args.get(arg, 0))) > cap:
                    entry["reason"] = f"{arg} {args.get(arg)} over limit {cap}"
                    raise ToolDenied(f"{tool}: {arg} over limit {cap}")
        entry["executed"] = True
        return {"ok": True, "tool": tool}

    @property
    def unauthorized_executions(self) -> int:
        """Executed calls that the policy would have refused (non-zero only with enforce=False)."""
        bad = 0
        for e in self.log:
            if not e["executed"]:
                continue
            caps = self.limits.get(e["tool"], {})
            over = any(abs(float(e["args"].get(a, 0))) > c for a, c in caps.items())
            unapproved = e["tool"] in self.needs_approval and not e["approved"]
            if e["tool"] not in self.allowed or unapproved or over:
                bad += 1
        return bad


class BudgetExceeded(Exception):
    pass


@dataclass
class Budget:
    max_tokens: int
    max_calls: int
    enforce: bool = True
    tokens: int = 0
    calls: int = 0

    def charge(self, tokens: int) -> None:
        """Refuse a call that would cross the cap, so spend never exceeds ``max_tokens``."""
        if self.enforce and (self.tokens + tokens > self.max_tokens or self.calls + 1 > self.max_calls):
            raise BudgetExceeded(f"budget: {self.tokens}+{tokens} tokens / {self.calls + 1} calls")
        self.tokens += tokens
        self.calls += 1
