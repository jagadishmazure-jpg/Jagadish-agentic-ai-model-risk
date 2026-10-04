"""Custom events in the shape Application Insights stores them (``name`` + ``customDimensions``).

The workbook in infra/workbook queries exactly these names:

    modelrisk.gate      one per model per gate run (ok, failed gates)
    modelrisk.scenario  one per scenario result (status, value, threshold)
    modelrisk.residual  one per risk after scenario feedback (residual, within_appetite)
    modelrisk.drift     one per monitoring window (psi_score, status)
    modelrisk.signoff   one per audit-log sign-off (stage, role, decision)

Offline, ``modelrisk telemetry`` writes them as JSON lines. On Azure the same dictionaries are
sent with the Azure Monitor OpenTelemetry distro (see docs/implementation-guide.md).
"""

from __future__ import annotations

from typing import Any

from modelrisk.combine import scenario_results, update_residuals
from modelrisk.monitoring import monitor
from modelrisk.registry import load_all
from modelrisk.signoff import read_log


def event(name: str, **dims: Any) -> dict[str, Any]:
    return {"name": name, "customDimensions": {k: v for k, v in dims.items()}}


def collect(gate: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if gate:
        for m in gate["models"]:
            out.append(event("modelrisk.gate", model=m["model"], ok=m["ok"], failed=",".join(c["gate"] for c in m["checks"] if not c["ok"])))
    for rec in load_all():
        res = scenario_results(rec)
        for r in res:
            out.append(
                event(
                    "modelrisk.scenario",
                    model=rec.id,
                    scenario=r["id"],
                    kind=r["kind"],
                    status=r["status"],
                    value=r["value"],
                    threshold=r["threshold"],
                )
            )
        for r in update_residuals(rec, res):
            out.append(
                event(
                    "modelrisk.residual",
                    model=rec.id,
                    risk=r["id"],
                    residual=r["residual"],
                    band=r["residual_band"],
                    within_appetite=r["within_appetite"],
                )
            )
        if rec.kind == "domain":
            m = monitor(rec)
            psi = next(c["value"] for c in m["checks"] if c["check"] == "psi:score")
            out.append(event("modelrisk.drift", model=rec.id, psi_score=psi, status=m["status"]))
    for e in read_log():
        if e["event"] == "signoff":
            out.append(event("modelrisk.signoff", model=e["model_id"], stage=e["stage"], role=e["role"], decision=e["decision"]))
    return out
