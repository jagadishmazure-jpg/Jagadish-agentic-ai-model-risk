"""Offline evaluation of a domain agent on a seeded synthetic set.

Used three ways: the numbers in each model card were produced by it (seed 7), independent
validation re-performs it on a fresh seed, and monitoring runs it on each production window.
"""

from __future__ import annotations

from typing import Any

from modelrisk.agents.base import AgentSpec, Controls, build


def evaluate(spec: AgentSpec, n: int = 1000, seed: int = 7, shift: float = 0.0,
             controls: Controls = Controls()) -> dict[str, Any]:
    cases = spec.generate(n, seed, shift=shift)
    agent = build(spec, controls)
    results = [agent.invoke(c) for c in cases]
    tp = fp = fn = tn = 0
    fav: dict[str, list[int]] = {}
    for r, c in zip(results, cases):
        pred, truth = r["decision"] in spec.positive, spec.label(c)
        tp += pred and truth
        fp += pred and not truth
        fn += (not pred) and truth
        tn += (not pred) and not truth
        fav.setdefault(c["group"], []).append(r["decision"] in spec.favorable)
    rates = {g: sum(v) / len(v) for g, v in fav.items()}
    return {
        "accuracy": round((tp + tn) / n, 4),
        "precision": round(tp / (tp + fp), 4) if tp + fp else 0.0,
        "recall": round(tp / (tp + fn), 4) if tp + fn else 0.0,
        "human_review_rate": round(sum(r["status"] != "done" for r in results) / n, 4),
        "adverse_impact_ratio": round(min(rates.values()) / max(rates.values()), 4) if max(rates.values()) else 1.0,
        "scores": [r["score"] for r in results],
        "features": {f: [c["x"][f] for c in cases] for f in spec.features},
    }


def metric(result: dict[str, Any], name: str) -> float:
    return result[name]
