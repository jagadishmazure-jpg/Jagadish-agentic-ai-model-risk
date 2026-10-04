"""A deterministic stand-in for a hosted model, with failure modes you can switch on.

The mock writes short rationales that cite the evidence ids it was given. Scenario knobs:
  * ``available=False``: every call raises ``ModelUnavailable`` (outage);
  * ``follow_injections=True``: an unsafe model that obeys instructions found in its input;
  * ``hallucinate_every``: every n-th rationale adds a claim with an unsupported citation;
  * ``echo_input=True``: the agent repeats raw input in its rationale (how PII leaks);
  * ``retry_storm``: tokens per call multiply (a looping or verbose agent).
Token counts are word counts x 1.3, which is close enough for cost scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ModelUnavailable(Exception):
    pass


@dataclass
class MockLLM:
    name: str = "gpt-4o (mock)"
    available: bool = True
    follow_injections: bool = False
    hallucinate_every: int = 0
    echo_input: bool = False
    retry_storm: int = 1
    calls: int = 0

    def complete(self, task: str, evidence: dict[str, str], untrusted: str = "") -> dict[str, Any]:
        if not self.available:
            raise ModelUnavailable(self.name)
        self.calls += 1
        cited = sorted(evidence)
        claims = [{"text": f"{task}: {evidence[k]}", "cites": [k]} for k in cited]
        if self.hallucinate_every and self.calls % self.hallucinate_every == 0:
            claims.append({"text": f"{task}: an exception applies under section 9.9", "cites": ["policy-9.9"]})
        text = " ".join(c["text"] for c in claims)
        obeyed = self.follow_injections and "ignore" in untrusted.lower()
        words = len(text.split()) + len(untrusted.split())
        return {"text": text, "claims": claims, "obeyed_injection": obeyed, "tokens": int(words * 1.3 * self.retry_storm) + 200}
