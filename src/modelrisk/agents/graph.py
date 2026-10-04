"""A tiny LangGraph-style state graph: nodes, plain and conditional edges, a step cap and HITL
interrupts. Offline and deterministic, so scenarios can replay an agent thousands of times.

    g = StateGraph()
    g.add_node("intake", intake)
    g.add_conditional_edges("score", lambda s: "hitl" if s["risky"] else "done")
    app = g.compile(entry="intake", max_steps=20)
    final = app.invoke({"case": ...})
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

END = "__end__"
State = dict[str, Any]


class StepLimitExceeded(RuntimeError):
    """Raised when a run exceeds ``max_steps``: the loop guard every agent gets for free."""


@dataclass
class CompiledGraph:
    nodes: dict[str, Callable[[State], State]]
    edges: dict[str, str]
    conditional: dict[str, Callable[[State], str]]
    entry: str
    max_steps: int

    def invoke(self, state: State) -> State:
        state = {**state, "trace": list(state.get("trace", []))}
        node, steps = self.entry, 0
        while node != END:
            steps += 1
            if steps > self.max_steps:
                raise StepLimitExceeded(f"more than {self.max_steps} steps (last node {node})")
            state = self.nodes[node](state)
            state["trace"].append(node)
            if state.get("interrupt"):  # human in the loop: stop and hand over
                state["status"] = "awaiting-human"
                return state
            node = self.conditional[node](state) if node in self.conditional else self.edges.get(node, END)
        state.setdefault("status", "done")
        return state


@dataclass
class StateGraph:
    nodes: dict[str, Callable[[State], State]] = field(default_factory=dict)
    edges: dict[str, str] = field(default_factory=dict)
    conditional: dict[str, Callable[[State], str]] = field(default_factory=dict)

    def add_node(self, name: str, fn: Callable[[State], State]) -> StateGraph:
        self.nodes[name] = fn
        return self

    def add_edge(self, src: str, dst: str) -> StateGraph:
        self.edges[src] = dst
        return self

    def add_conditional_edges(self, src: str, router: Callable[[State], str]) -> StateGraph:
        self.conditional[src] = router
        return self

    def compile(self, entry: str, max_steps: int = 25) -> CompiledGraph:
        missing = {d for d in self.edges.values() if d != END and d not in self.nodes}
        if missing or entry not in self.nodes:
            raise ValueError(f"unknown nodes: {sorted(missing) or entry}")
        return CompiledGraph(dict(self.nodes), dict(self.edges), dict(self.conditional), entry, max_steps)
