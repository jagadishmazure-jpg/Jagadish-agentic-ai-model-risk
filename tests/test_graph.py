import pytest

from modelrisk.agents.graph import END, StateGraph, StepLimitExceeded


def inc(s):
    return {**s, "n": s.get("n", 0) + 1}


def test_linear_graph_runs_in_order():
    g = StateGraph().add_node("a", inc).add_node("b", inc).add_edge("a", "b").add_edge("b", END)
    out = g.compile("a").invoke({})
    assert out["n"] == 2 and out["trace"] == ["a", "b"] and out["status"] == "done"


def test_conditional_edge_routes_on_state():
    g = StateGraph().add_node("a", inc).add_node("hi", inc).add_node("lo", lambda s: s)
    g.add_conditional_edges("a", lambda s: "hi" if s["n"] > 0 else "lo")
    out = g.compile("a").invoke({})
    assert out["trace"] == ["a", "hi"]


def test_step_cap_stops_loops():
    g = StateGraph().add_node("a", inc).add_edge("a", "a")
    with pytest.raises(StepLimitExceeded):
        g.compile("a", max_steps=5).invoke({})


def test_interrupt_hands_over_to_a_human():
    g = StateGraph().add_node("a", lambda s: {**s, "interrupt": True}).add_node("b", inc).add_edge("a", "b")
    out = g.compile("a").invoke({})
    assert out["status"] == "awaiting-human" and out["trace"] == ["a"]


def test_unknown_edge_target_is_rejected_at_compile_time():
    with pytest.raises(ValueError):
        StateGraph().add_node("a", inc).add_edge("a", "missing").compile("a")


def test_unknown_entry_is_rejected():
    with pytest.raises(ValueError):
        StateGraph().add_node("a", inc).compile("zzz")


def test_invoke_does_not_mutate_the_input_trace():
    g = StateGraph().add_node("a", inc)
    start = {"trace": ["before"]}
    g.compile("a").invoke(start)
    assert start["trace"] == ["before"]
