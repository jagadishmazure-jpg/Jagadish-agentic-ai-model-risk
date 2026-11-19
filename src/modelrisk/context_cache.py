"""Save completed agent steps so a new worker does not repeat those model calls.

The cache stores the output of each completed step, keyed by the session, the
step and the payload. A new worker loads that state. A step whose key is
already present is not sent to the model again. A different payload is a
different key, so it is a new call rather than a reused one.

Offline, on the mock model. A hosted cache that restores GPU context is a
different product and is not called here.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from modelrisk.agents.llm import MockLLM

PLAN: tuple[dict[str, str], ...] = (
    {"id": "extract", "kind": "model", "task": "extract documented features"},
    {"id": "score", "kind": "local", "task": "apply the documented score"},
    {"id": "explain", "kind": "model", "task": "write a rationale from the score"},
    {"id": "cite", "kind": "model", "task": "cite only supplied evidence"},
)

DEMO_EVIDENCE = {"memo": "dispute on a card-present purchase", "policy": "a middle-band score goes to a person"}


class ResumeMismatch(Exception):
    pass


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def call_key(session_id: str, step_id: str, payload: dict[str, Any]) -> str:
    """Identity of one model call. A changed payload must not reuse the old output."""
    body = _canonical({"payload": payload, "session": session_id, "step": step_id})
    return hashlib.sha256(body.encode()).hexdigest()


def count_duplicates(keys: list[str]) -> int:
    return len(keys) - len(set(keys))


@dataclass
class StepRecord:
    step_id: str
    kind: str
    call_key: str
    output: dict[str, Any]


@dataclass
class WorkState:
    session_id: str
    model_id: str
    case_id: str
    steps: list[StepRecord] = field(default_factory=list)


class ContextCache:
    def __init__(self) -> None:
        self._states: dict[str, WorkState] = {}

    def save(self, state: WorkState) -> None:
        self._states[state.session_id] = copy.deepcopy(state)

    def load(self, session_id: str) -> WorkState | None:
        state = self._states.get(session_id)
        return copy.deepcopy(state) if state is not None else None


def run_plan(
    llm: MockLLM,
    cache: ContextCache,
    session_id: str,
    model_id: str,
    case_id: str,
    evidence: dict[str, str],
    stop_after: str | None = None,
) -> tuple[WorkState, list[str]]:
    """Run ``PLAN``, skipping model steps whose call key is already saved.

    Returns the state and the call keys this worker actually sent to the model.
    """
    state = cache.load(session_id)
    if state is None:
        state = WorkState(session_id, model_id, case_id)
    elif state.model_id != model_id or state.case_id != case_id:
        raise ResumeMismatch(f"{session_id} belongs to {state.model_id}/{state.case_id}")
    by_id = {step.step_id: step for step in state.steps}
    invoked: list[str] = []
    for step in PLAN:
        if step["kind"] == "model":
            key = call_key(session_id, step["id"], {"evidence": evidence, "task": step["task"]})
            prior = by_id.get(step["id"])
            if prior is not None and prior.call_key == key:
                if stop_after == step["id"]:
                    break
                continue
            output = llm.complete(step["task"], evidence)
            invoked.append(key)
            by_id[step["id"]] = StepRecord(step["id"], "model", key, output)
        elif step["id"] not in by_id:
            by_id[step["id"]] = StepRecord(step["id"], "local", "", {"ok": True})
        state.steps = [by_id[item["id"]] for item in PLAN if item["id"] in by_id]
        cache.save(state)
        if stop_after == step["id"]:
            break
    return state, invoked


def demo() -> dict[str, Any]:
    """Worker A stops after extract. Worker B finishes the plan on a new mock."""
    cache = ContextCache()
    session, model, case = "ses-cache", "halcyon-fraud-triage", "CASE-7"
    llm_a = MockLLM(name="worker-a")
    state_a, keys_a = run_plan(llm_a, cache, session, model, case, DEMO_EVIDENCE, stop_after="extract")
    llm_b = MockLLM(name="worker-b")
    state_b, keys_b = run_plan(llm_b, cache, session, model, case, DEMO_EVIDENCE)
    saved = next(step for step in state_a.steps if step.step_id == "extract")
    resumed = next(step for step in state_b.steps if step.step_id == "extract")
    return {
        "session_id": session,
        "model_id": model,
        "case_id": case,
        "stopped_after": "extract",
        "calls": {"worker-a": len(keys_a), "worker-b": len(keys_b)},
        "duplicate_model_calls": count_duplicates(keys_a + keys_b),
        "model_steps": [step.step_id for step in state_b.steps if step.kind == "model"],
        "reused_saved_output": resumed.output == saved.output and resumed.call_key not in keys_b,
    }


def render_demo(result: dict[str, Any] | None = None) -> str:
    result = demo() if result is None else result
    calls = result["calls"]
    reused = "yes" if result["reused_saved_output"] else "no"
    return "\n".join(
        [
            f"session {result['session_id']} model {result['model_id']} case {result['case_id']}",
            f"worker-a stopped after {result['stopped_after']}; model calls {calls['worker-a']}",
            f"worker-b resumed; model calls {calls['worker-b']}",
            f"duplicate model calls: {result['duplicate_model_calls']}",
            f"reused saved output: {reused}",
            "model steps: " + ", ".join(result["model_steps"]),
        ]
    )
