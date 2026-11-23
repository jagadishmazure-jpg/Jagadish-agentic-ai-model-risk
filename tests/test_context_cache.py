import pytest

from modelrisk.agents.llm import MockLLM
from modelrisk.context_cache import (
    PLAN,
    ContextCache,
    ResumeMismatch,
    call_key,
    count_duplicates,
    demo,
    run_plan,
)

EVIDENCE = {"memo": "dispute on a card-present purchase", "policy": "a middle-band score goes to a person"}


def _run(cache, llm, session="ses-cache", model="halcyon-fraud-triage", case="CASE-7", evidence=None, stop_after=None):
    return run_plan(llm, cache, session, model, case, EVIDENCE if evidence is None else evidence, stop_after)


def test_resume_does_not_repeat_completed_model_calls():
    cache = ContextCache()
    llm_a, llm_b = MockLLM(name="worker-a"), MockLLM(name="worker-b")
    state_a, keys_a = _run(cache, llm_a, stop_after="extract")
    state_b, keys_b = _run(cache, llm_b)
    assert llm_a.calls == 1 and keys_a and llm_b.calls == 2
    assert count_duplicates(keys_a + keys_b) == 0
    assert set(keys_a).isdisjoint(keys_b)
    extract_a = next(step for step in state_a.steps if step.step_id == "extract")
    extract_b = next(step for step in state_b.steps if step.step_id == "extract")
    assert extract_b.output == extract_a.output
    assert [step.step_id for step in state_b.steps if step.kind == "model"] == ["extract", "explain", "cite"]


@pytest.mark.parametrize("stop_after,first,second", [("extract", 1, 2), ("explain", 2, 1), ("cite", 3, 0)])
def test_a_new_worker_only_calls_the_model_for_missing_steps(stop_after, first, second):
    cache = ContextCache()
    _, keys_a = _run(cache, MockLLM(), stop_after=stop_after)
    _, keys_b = _run(cache, MockLLM())
    assert len(keys_a) == first and len(keys_b) == second
    assert count_duplicates(keys_a + keys_b) == 0


def test_finished_work_resumes_with_zero_model_calls():
    cache = ContextCache()
    _run(cache, MockLLM())
    llm_b = MockLLM(name="worker-b")
    _, keys_b = _run(cache, llm_b)
    assert keys_b == [] and llm_b.calls == 0


def test_changed_input_is_a_new_call_not_a_cached_one():
    cache = ContextCache()
    _, keys_a = _run(cache, MockLLM(), evidence=EVIDENCE)
    changed = {"memo": "a second dispute", "policy": EVIDENCE["policy"]}
    llm_b = MockLLM()
    _, keys_b = _run(cache, llm_b, evidence=changed)
    assert llm_b.calls == 3
    assert set(keys_a).isdisjoint(keys_b)
    assert count_duplicates(keys_b) == 0


def test_another_session_does_not_reuse_saved_steps():
    cache = ContextCache()
    _run(cache, MockLLM(), stop_after="extract")
    llm = MockLLM()
    _, keys = _run(cache, llm, session="ses-other")
    assert llm.calls == 3 and len(keys) == 3


def test_resume_refuses_a_different_model_or_case():
    cache = ContextCache()
    _run(cache, MockLLM(), stop_after="extract")
    with pytest.raises(ResumeMismatch):
        _run(cache, MockLLM(), model="juniper-prior-auth")
    with pytest.raises(ResumeMismatch):
        _run(cache, MockLLM(), case="CASE-8")


def test_loaded_state_is_a_copy():
    cache = ContextCache()
    _run(cache, MockLLM(), stop_after="extract")
    loaded = cache.load("ses-cache")
    loaded.steps.clear()
    assert cache.load("ses-cache").steps


def test_call_key_changes_with_the_payload_and_is_stable():
    payload = {"evidence": EVIDENCE, "task": "extract documented features"}
    assert call_key("ses-cache", "extract", payload) == call_key("ses-cache", "extract", payload)
    assert call_key("ses-cache", "extract", payload) != call_key("ses-other", "extract", payload)
    assert call_key("ses-cache", "extract", payload) != call_key("ses-cache", "explain", payload)


def test_local_score_does_not_call_the_model():
    cache = ContextCache()
    llm = MockLLM()
    state, keys = _run(cache, llm, stop_after="score")
    assert llm.calls == 1 and len(keys) == 1
    assert any(step.step_id == "score" and step.kind == "local" for step in state.steps)


def test_plan_has_three_model_steps():
    assert [step["id"] for step in PLAN if step["kind"] == "model"] == ["extract", "explain", "cite"]


def test_demo_proves_no_duplicate_calls():
    result = demo()
    assert result["duplicate_model_calls"] == 0
    assert result["calls"] == {"worker-a": 1, "worker-b": 2}
    assert result["reused_saved_output"] is True
