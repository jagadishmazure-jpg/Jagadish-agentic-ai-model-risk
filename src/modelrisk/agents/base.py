"""The shared agent graph every domain plugs into.

    intake -> screen -> features -> score -> explain -> act -> route -> (HITL interrupt | done)

A domain supplies an ``AgentSpec``: synthetic data, the scoring model, decision rules, evidence,
tool policy and which decisions always need a human. ``Controls`` holds the runtime mitigations
that risk cards cite; scenarios switch individual controls off to run a what-if.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

from modelrisk.agents.graph import StateGraph
from modelrisk.agents.guardrails import (
    PII_KINDS,
    Budget,
    BudgetExceeded,
    ToolDenied,
    ToolPolicy,
    mask,
    screen,
)
from modelrisk.agents.llm import MockLLM, ModelUnavailable

PRICE_PER_1K_TOKENS = 0.01  # USD, blended input/output rate used for the cost scenarios


@dataclass(frozen=True)
class Controls:
    """Runtime mitigations. Every flag maps to a control id on the domain risk cards."""

    screen_injection: bool = True  # untrusted text is screened and quoted, never obeyed
    enforce_tools: bool = True  # allow-list, approval-required tools, argument limits
    fallback: bool = True  # model outage -> rules fallback + human queue
    verify_claims: bool = True  # every claim must cite supplied evidence
    mask_output: bool = True  # PII/PHI masking on everything the agent emits
    budget: bool = True  # token/call cap per task
    ood_guard: bool = True  # inputs outside the data-sheet ranges go to a human
    exclude_proxies: bool = True  # protected attributes and proxies never reach the model

    def without(self, *names: str) -> Controls:
        return replace(self, **{n: False for n in names})


@dataclass
class AgentSpec:
    id: str
    company: str
    task: str
    features: list[str]
    ranges: dict[str, tuple[float, float]]
    weights: dict[str, float]
    bias: float
    proxy_weights: dict[str, float]
    decide: Callable[[float, dict[str, Any]], str]
    action: Callable[[str, dict[str, Any]], tuple[str, dict[str, Any]]]
    generate: Callable[..., list[dict[str, Any]]]
    label: Callable[[dict[str, Any]], bool]
    positive: set[str]
    evidence: Callable[[dict[str, Any], str], dict[str, str]]
    policy: Callable[[bool], ToolPolicy]
    favorable: set[str]
    hitl_decisions: set[str] = field(default_factory=set)
    mask_kinds: tuple[str, ...] = PII_KINDS
    max_tokens: int = 4000
    max_calls: int = 6
    notice: str = ""

    def norm(self, name: str, value: float) -> float:
        lo, hi = self.ranges[name]
        return (value - lo) / (hi - lo) if hi > lo else 0.0

    def probability(self, x: dict[str, float], use_proxies: bool = False) -> float:
        z = self.bias + sum(w * self.norm(f, x[f]) for f, w in self.weights.items())
        if use_proxies:
            z += sum(w * x.get(f, 0.0) for f, w in self.proxy_weights.items())
        return 1 / (1 + math.exp(-z))


def out_of_range(spec: AgentSpec, x: dict[str, float]) -> list[str]:
    return [f for f in spec.features if not (spec.ranges[f][0] <= x[f] <= spec.ranges[f][1])]


def build(spec: AgentSpec, controls: Controls | None = None, llm: MockLLM | None = None, max_steps: int = 20):
    """Compile the domain agent. Returns a graph whose ``invoke(case)`` gives the final state."""
    controls = controls or Controls()
    llm = llm or MockLLM()

    def intake(s):
        c = s["case"]
        return {**s, "flags": [], "tools": [], "tokens": 0, "untrusted": c.get("untrusted", "")}

    def screen_node(s):
        if controls.screen_injection:
            r = screen(s["untrusted"])
            if r["flagged"]:
                s["flags"].append("injection-screened")
                s["untrusted"] = "[quoted untrusted text withheld from the model]"
        return s

    def features(s):
        x = s["case"]["x"]
        s["x"] = {f: x[f] for f in spec.features}
        if not controls.exclude_proxies:
            s["x"].update({f: x[f] for f in spec.proxy_weights})
        bad = out_of_range(spec, x)
        if bad and controls.ood_guard:
            s["flags"].append("out-of-range:" + ",".join(bad))
        return s

    def score(s):
        p = spec.probability(s["case"]["x"], use_proxies=not controls.exclude_proxies)
        s["score"] = round(p, 4)
        s["decision"] = spec.decide(p, s["case"])
        contrib = {f: w * spec.norm(f, s["case"]["x"][f]) for f, w in spec.weights.items()}
        s["key_factors"] = sorted(contrib, key=lambda f: contrib[f])[:3]
        return s

    def explain(s):
        budget = Budget(spec.max_tokens, spec.max_calls, enforce=controls.budget)
        ev = spec.evidence(s["case"], s["decision"])
        s["evidence_ids"] = sorted(ev)
        out = None
        try:
            for _ in range(1 + int(s["case"].get("reasks", 0))):
                out = llm.complete(spec.task, ev, s["untrusted"])
                budget.charge(out["tokens"])
        except ModelUnavailable:
            if not controls.fallback:
                raise
            s["flags"].append("model-outage-fallback")
            s["rationale"] = f"Rules fallback: score {s['score']} -> {s['decision']}. Queued for a human."
            s["claims"] = []
            return s
        except BudgetExceeded:
            s["flags"].append("budget-stop")
        s["tokens"] = budget.tokens
        out = out or {"text": "", "claims": [], "obeyed_injection": False}
        claims = out["claims"]
        if controls.verify_claims:
            supported = [c for c in claims if set(c["cites"]) <= set(ev)]
            if len(supported) < len(claims):
                s["flags"].append("unsupported-claim-removed")
            claims = supported
        s["claims"] = claims
        s["rationale"] = out["text"] if not controls.verify_claims else f"{spec.task}: " + "; ".join(c["text"] for c in claims)
        if llm.echo_input and s["case"].get("untrusted"):
            s["rationale"] += " Input: " + s["case"]["untrusted"]
        if out["obeyed_injection"]:
            s["decision"] = s["case"].get("attack_goal", s["decision"])
            s["injected"] = True
        return s

    def act(s):
        if "model-outage-fallback" in s["flags"]:
            return s
        tool, args = s["case"].get("llm_plan") or spec.action(s["decision"], s["case"])
        if not tool:
            return s
        policy = spec.policy(controls.enforce_tools)
        if controls.enforce_tools and tool in policy.needs_approval:
            s["pending_action"] = {"tool": tool, "args": args}  # executed only after human approval
            return s
        try:
            policy.call(tool, approved=False, **args)
        except ToolDenied as e:
            s["flags"].append(f"tool-denied:{e}")
        s["tools"] = policy.log
        s["unauthorized"] = policy.unauthorized_executions
        return s

    def route(s):
        needs_human = bool(s["flags"]) or s["decision"] in spec.hitl_decisions or "pending_action" in s
        s["output"] = mask(s.get("rationale", ""), spec.mask_kinds) if controls.mask_output else s.get("rationale", "")
        s["cost_usd"] = round(s["tokens"] / 1000 * PRICE_PER_1K_TOKENS, 4)
        if needs_human:
            s["interrupt"] = True
        return s

    g = StateGraph()
    for name, fn in [
        ("intake", intake),
        ("screen", screen_node),
        ("features", features),
        ("score", score),
        ("explain", explain),
        ("act", act),
        ("route", route),
    ]:
        g.add_node(name, fn)
    for a, b in [("intake", "screen"), ("screen", "features"), ("features", "score"), ("score", "explain"), ("explain", "act"), ("act", "route")]:
        g.add_edge(a, b)
    app = g.compile(entry="intake", max_steps=max_steps)

    class Agent:
        graph = app

        @staticmethod
        def invoke(case: dict[str, Any]) -> dict[str, Any]:
            return app.invoke({"case": case})

    return Agent


def rng(seed: int) -> random.Random:
    return random.Random(seed)


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))
