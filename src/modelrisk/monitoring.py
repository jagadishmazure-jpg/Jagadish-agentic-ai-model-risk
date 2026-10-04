"""Ongoing monitoring: drift (PSI) and performance thresholds per production window.

For each window the monitor compares feature and score distributions with the reference set
(seed 7) and computes the card's performance metric on the window's labels (in production,
labels arrive later: chargebacks, adjuster outcomes, clinician decisions).

    PSI < psi_warn            ok
    psi_warn <= PSI < alert   warn  -> watch, open a P2 backlog item
    PSI >= psi_alert          alert -> on_alert action from the model card
    metric < warn             warn
    metric < min              alert
"""

from __future__ import annotations

from typing import Any

from modelrisk.agents.registry import SPECS
from modelrisk.evaluation import evaluate
from modelrisk.registry import ModelRecord
from modelrisk.scenarios.engine import psi

LEVEL = {"ok": 0, "warn": 1, "alert": 2}


def _psi_status(v: float, warn: float, alert: float) -> str:
    return "alert" if v >= alert else "warn" if v >= warn else "ok"


def monitor(rec: ModelRecord, seed: int = 101, shift: float = 0.0) -> dict[str, Any]:
    if rec.kind != "domain":
        return {"model": rec.id, "status": "external", "checks": [], "action": "monitored in the source repository"}
    cfg = rec.model_card["monitoring"]
    spec = SPECS[rec.id]
    ref = evaluate(spec, seed=7)
    cur = evaluate(spec, n=cfg["window"], seed=seed, shift=shift)
    checks = []
    for f in spec.features:
        v = psi(ref["features"][f], cur["features"][f])
        checks.append({"check": f"psi:{f}", "value": v, "status": _psi_status(v, cfg["psi_warn"], cfg["psi_alert"])})
    v = psi(ref["scores"], cur["scores"])
    checks.append({"check": "psi:score", "value": v, "status": _psi_status(v, cfg["psi_warn"], cfg["psi_alert"])})
    for p in cfg["performance"]:
        val = cur[p["metric"]]
        st = "alert" if val < p["min"] else "warn" if val < p["warn"] else "ok"
        checks.append({"check": f"perf:{p['metric']}", "value": val, "status": st, "min": p["min"], "warn": p["warn"]})
    overall = max((c["status"] for c in checks), key=LEVEL.get)
    action = {"ok": "none", "warn": "watch next window; P2 backlog item", "alert": cfg["on_alert"]}[overall]
    return {"model": rec.id, "window": cfg["window"], "seed": seed, "shift": shift, "status": overall, "checks": checks, "action": action}
