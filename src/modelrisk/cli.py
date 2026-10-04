"""``modelrisk`` command line. Every command is offline and read-only except ``signoff``.

modelrisk inventory | model ID | risks | heatmap | scenarios --model ID [--mitigations off]
modelrisk whatif --model ID | combine --model ID | validate --model ID | monitor --model ID
modelrisk lifecycle | gate | regmap | portfolio | agent --model ID | signoff ... | mcp | mcp-demo
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from modelrisk import REGULATORY, ROOT
from modelrisk.report import heatmap_text, table
from modelrisk.scenarios.engine import KIND_CONTROLS


def _p(text: str = "") -> None:
    print(text)


def cmd_inventory(a) -> int:
    from modelrisk.registry import load_all
    from modelrisk.tiering import eu_ai_act_class, materiality, tier

    rows = [
        {
            "id": r.id,
            "domain": r.model_card["domain"],
            "company": r.model_card["company"][:28],
            "stage": r.stage,
            "tier": tier(r.model_card),
            "points": sum(materiality(r.model_card).values()),
            "eu": eu_ai_act_class(r.model_card),
        }
        for r in load_all()
    ]
    _p(table(rows, ["id", "domain", "stage", "tier", "points", "eu"], ["model", "domain", "stage", "tier", "points", "EU AI Act"]))
    return 0


def cmd_model(a) -> int:
    from modelrisk.registry import load
    from modelrisk.tiering import eu_ai_act_class, materiality, tier

    r = load(a.model_id)
    c = r.model_card
    _p(f"{c['name']} ({c['id']} v{c['version']}), {c['company']}")
    _p(f"purpose: {c['purpose']}")
    _p(f"autonomy: {c['system']['autonomy']}; tools: {', '.join(c['system']['tools'])}")
    _p(f"fallback: {c['system']['fallback']}")
    _p(f"tier {tier(c)} (materiality {materiality(c)}), EU AI Act: {eu_ai_act_class(c)}, stage: {r.stage}")
    _p(table([{**m, "value": m["value"], "threshold": m["threshold"]} for m in c["metrics"]], ["name", "value", "threshold", "direction"]))
    for n in c.get("notices", []):
        _p(f"notice: {n}")
    if c.get("governs"):
        _p(f"governs: {c['governs']}")
    return 0


def cmd_risks(a) -> int:
    from modelrisk.mcp_server import query

    rows = query(a.model, a.band)
    for r in rows:
        r["inh"] = f"{r['inherent']} {r['inherent_band']}"
        r["res"] = f"{r['residual']} {r['residual_band']}"
        r["owner_short"] = r["owner"].split(" (")[0][:24]
    _p(
        table(
            rows,
            ["model", "id", "category", "likelihood", "impact", "inh", "implemented_controls", "res", "owner_short"],
            ["model", "risk", "category", "L", "I", "inherent", "controls", "residual", "owner"],
        )
    )
    _p(f"{len(rows)} risks")
    return 0


def cmd_heatmap(a) -> int:
    from modelrisk.mcp_server import query
    from modelrisk.scoring import heatmap

    rows = query(a.model)
    _p(heatmap_text(heatmap(rows), f"inherent risk heatmap: {a.model or 'all models'} ({len(rows)} risks)"))
    return 0


def _scen_rows(model_id: str, mitigations: bool) -> list[dict[str, Any]]:
    from modelrisk.combine import scenario_results
    from modelrisk.registry import load

    return scenario_results(load(model_id), mitigations=mitigations)


def cmd_scenarios(a) -> int:
    rows = _scen_rows(a.model, a.mitigations == "on")
    _p(table(rows, ["id", "kind", "metric", "value", "threshold", "status"]))
    if a.details:
        for r in rows:
            _p(f"{r['id']}: {json.dumps(r['details'], sort_keys=True)}")
    return 0


def cmd_whatif(a) -> int:
    on, off = _scen_rows(a.model, True), _scen_rows(a.model, False)
    rows = [
        {
            "id": x["id"],
            "kind": x["kind"],
            "metric": x["metric"],
            "on": f"{x['value']} {x['status']}",
            "off": f"{y['value']} {y['status']}",
            "controls_off": y["mitigations"].replace("off: ", ""),
        }
        for x, y in zip(on, off, strict=True)
    ]
    _p(table(rows, ["id", "kind", "metric", "on", "off", "controls_off"], ["id", "kind", "metric", "controls on", "controls off", "switched off"]))
    return 0


def cmd_family(a) -> int:
    """One scenario family across every domain model: value with controls on and off, plus details."""
    from modelrisk.agents.registry import SPECS

    rows, details = [], []
    for model_id in SPECS:
        on = [x for x in _scen_rows(model_id, True) if x["kind"] == a.kind]
        off = {y["id"]: y for y in _scen_rows(model_id, False) if y["kind"] == a.kind}
        for x in on:
            y = off[x["id"]]
            rows.append(
                {
                    "model": model_id,
                    "id": x["id"],
                    "metric": x["metric"],
                    "threshold": x["threshold"],
                    "on": f"{x['value']} {x['status']}",
                    "off": f"{y['value']} {y['status']}",
                }
            )
            details.append(f"{x['id']} on:  {json.dumps(x['details'], sort_keys=True)}")
            details.append(f"{x['id']} off: {json.dumps(y['details'], sort_keys=True)}")
    _p(table(rows, ["model", "id", "metric", "threshold", "on", "off"], ["model", "id", "metric", "threshold", "controls on", "controls off"]))
    if a.details:
        for line in details:
            _p(line)
    return 0


def cmd_combine(a) -> int:
    from modelrisk.combine import summary
    from modelrisk.registry import load

    s = summary(load(a.model))
    _p("1. model card -> risk cards")
    _p(
        table(
            [{**x, "covered_by": ",".join(x["covered_by"]) or "-", "ok": "ok" if x["ok"] else "MISSING"} for x in s["1_model_card_to_risks"]],
            ["kind", "reason", "covered_by", "ok"],
        )
    )
    _p("\n2. data sheet -> model understanding")
    _p(table([{**x, "ok": "ok" if x["ok"] else "FAIL"} for x in s["2_data_sheet_understanding"]], ["id", "ok", "detail"]))
    _p("\n3. risk cards -> scenarios")
    _p(
        table(
            [{**x, "scenarios": ",".join(x["scenarios"]), "ok": "ok" if x["ok"] else "FAIL"} for x in s["3_risks_to_scenarios"]],
            ["risk", "material", "scenarios", "ok"],
        )
    )
    _p("\n4. scenario results -> residual risk")
    _p(
        table(
            s["4_residuals"],
            ["id", "inherent", "residual_before", "scenario_status", "residual", "residual_band", "within_appetite"],
            ["risk", "inherent", "residual (card)", "scenarios", "residual (tested)", "band", "in appetite"],
        )
    )
    _p("\n4. development backlog")
    _p(table(s["4_backlog"], ["priority", "source", "item"]) if s["4_backlog"] else "(empty)")
    return 0


def cmd_validate(a) -> int:
    from modelrisk.registry import load
    from modelrisk.validation import validate

    v = validate(load(a.model), a.validator, a.team)
    _p(f"validation of {v['model']} by {v['validator']} ({v['team']}): {v['outcome']}")
    _p(table([{**f, "ok": "ok" if f["ok"] else "finding"} for f in v["findings"]], ["id", "ok", "severity", "detail"]))
    return 0 if v["outcome"] != "fail" else 1


def cmd_monitor(a) -> int:
    from modelrisk.monitoring import monitor
    from modelrisk.registry import load

    m = monitor(load(a.model), seed=a.seed, shift=a.shift)
    _p(f"monitoring window for {m['model']}: {m['window']} cases, shift {m['shift']} -> {m['status'].upper()}")
    _p(table(m["checks"], ["check", "value", "status"]))
    _p(f"action: {m['action']}")
    return 0


def cmd_lifecycle(a) -> int:
    from modelrisk.combine import scenario_results
    from modelrisk.gate import validation_outcome
    from modelrisk.lifecycle import stage_status
    from modelrisk.registry import load_all

    rows = []
    for r in load_all():
        st = stage_status(r, [x["status"] for x in scenario_results(r)], validation_outcome(r.id))
        rows.append(
            {
                "model": r.id,
                "stage": r.stage,
                "tier": st["tier"],
                "gates": "pass" if st["ok"] else "FAIL",
                "next": st["next_stage"] or "-",
                "blockers": ", ".join(c["check"].replace("sign-off: ", "") for c in st["next_blockers"]) or "-",
            }
        )
    _p(
        table(
            rows,
            ["model", "stage", "tier", "gates", "next", "blockers"],
            ["model", "stage", "tier", "current gates", "next stage", "next-stage blockers"],
        )
    )
    return 0


def cmd_gate(a) -> int:
    from modelrisk.gate import run_gate

    g = run_gate()
    if a.json:
        _p(json.dumps(g, indent=2, default=str))
        return 0 if g["ok"] else 1
    rows = [{"model": m["model"], **{c["gate"].split("-")[0]: "ok" if c["ok"] else "FAIL" for c in m["checks"]}} for m in g["models"]]
    _p(table(rows, ["model", "G1", "G2", "G3", "G4", "G5", "G6", "G7"]))
    for c in g["global"]:
        _p(f"{c['gate']}: {'ok' if c['ok'] else 'FAIL'}")
    for m in g["models"]:
        for c in m["checks"]:
            if not c["ok"]:
                _p(f"FAIL {m['model']} {c['gate']}: {c['detail']}")
    _p(f"gate: {'PASS' if g['ok'] else 'FAIL'}")
    return 0 if g["ok"] else 1


def cmd_regmap(a) -> int:
    doc = yaml.safe_load((REGULATORY / "mapping.yaml").read_text())
    for f in doc["frameworks"]:
        if a.framework and f["id"] != a.framework:
            continue
        _p(f"{f['id']}: {f['name']} ({len(f['items'])} controls)")
        if a.framework:
            _p(table([{**i, "implemented_by": ", ".join(i["implemented_by"])} for i in f["items"]], ["ref", "implemented_by"]))
    return 0


def cmd_portfolio(a) -> int:
    from modelrisk.combine import scenario_results
    from modelrisk.registry import load_all
    from modelrisk.tiering import tier

    rows = []
    for r in load_all():
        if r.kind != "portfolio":
            continue
        res = scenario_results(r)
        rows.append(
            {
                "model": r.id,
                "tier": tier(r.model_card),
                "stage": r.stage,
                "risks": len(r.risks()),
                "scenarios": ", ".join(f"{x['id']} {x['status']}" for x in res),
                "governs": r.model_card["governs"].replace("https://github.com/jagadishmazure-jpg/", ""),
            }
        )
        if a.verify:
            for x in res:
                local = ROOT.parent / x["details"]["repo"].replace("Jagadish-", "")
                if local.exists():
                    code = subprocess.call([sys.executable, "-m", "pytest", "-q", *x["details"]["tests"]], cwd=local)
                    _p(f"verify {x['id']} in {local}: {'pass' if code == 0 else 'FAIL'}")
                else:
                    _p(f"verify {x['id']}: no local checkout at {local}; attested result stands")
    _p(table(rows, ["model", "tier", "stage", "risks", "scenarios", "governs"]))
    return 0


def cmd_agent(a) -> int:
    from modelrisk.agents.base import build
    from modelrisk.agents.registry import SPECS

    spec = SPECS[a.model]
    case = spec.generate(a.case + 1, a.seed)[a.case]
    if a.untrusted:
        case = {**case, "untrusted": a.untrusted}
    s = build(spec).invoke(case)
    _p(f"case {case['id']} -> {s['decision']} (score {s['score']}), status {s['status']}")
    _p(f"trace: {' > '.join(s['trace'])}")
    _p(f"flags: {s['flags'] or '-'}")
    _p(f"key factors: {', '.join(s['key_factors'])}")
    if s.get("pending_action"):
        _p(f"pending human approval: {s['pending_action']['tool']}")
    _p(f"output: {s['output']}")
    if spec.notice:
        _p(f"notice: {spec.notice}")
    return 0


def cmd_signoff(a) -> int:
    from modelrisk.registry import load
    from modelrisk.signoff import SignoffRefused, request, sign, stale_signoffs, verify_chain

    if a.action == "verify":
        from modelrisk.registry import load_all

        _p(f"audit chain: {verify_chain()}")
        stale = {r.id: stale_signoffs(r) for r in load_all()}
        _p("stale sign-offs: " + (json.dumps({k: v for k, v in stale.items() if v}) if any(stale.values()) else "none"))
        return 0
    rec = load(a.model)
    if a.action == "request":
        e = request(rec, a.stage, a.by)
        _p(f"requested {a.stage} sign-off for {rec.id}; digest {e['digest'][:12]}; audit #{e['seq']}")
        return 0
    try:
        s = sign(rec, a.stage, a.role, a.approver, "reject" if a.reject else "approve", a.comment)
    except SignoffRefused as e:
        _p(f"refused: {e}")
        return 2
    _p(f"{s['decision']} by {s['approver']} as {s['role']} for {rec.id}/{a.stage}; digest {s['digest'][:12]}")
    return 0


def cmd_telemetry(a) -> int:
    from collections import Counter

    from modelrisk.gate import run_gate
    from modelrisk.telemetry import collect

    events = collect(run_gate())
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in events))
    for name, n in sorted(Counter(e["name"] for e in events).items()):
        _p(f"{name:<20} {n}")
    _p(f"{len(events)} events" + (f" written to {a.out}" if a.out else ""))
    return 0


def cmd_iac(a) -> int:
    from modelrisk.iac import PARTS

    for line in PARTS[a.part]():
        _p(line.rstrip())
    return 0


def cmd_mcp(a) -> int:
    from modelrisk.mcp_server import build_server

    build_server().run()
    return 0


def cmd_mcp_demo(a) -> int:
    from modelrisk.mcp_server import demo

    for line in asyncio.run(demo()):
        _p(line)
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="modelrisk", description="AI model risk management as code")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("inventory").set_defaults(fn=cmd_inventory)
    s = sub.add_parser("model")
    s.add_argument("model_id")
    s.set_defaults(fn=cmd_model)
    s = sub.add_parser("risks")
    s.add_argument("--model")
    s.add_argument("--band", default="low")
    s.set_defaults(fn=cmd_risks)
    s = sub.add_parser("heatmap")
    s.add_argument("--model")
    s.set_defaults(fn=cmd_heatmap)
    s = sub.add_parser("scenarios")
    s.add_argument("--model", required=True)
    s.add_argument("--mitigations", choices=["on", "off"], default="on")
    s.add_argument("--details", action="store_true")
    s.set_defaults(fn=cmd_scenarios)
    s = sub.add_parser("family")
    s.add_argument("--kind", required=True, choices=sorted(KIND_CONTROLS))
    s.add_argument("--details", action="store_true")
    s.set_defaults(fn=cmd_family)
    for name, fn in [("whatif", cmd_whatif), ("combine", cmd_combine)]:
        s = sub.add_parser(name)
        s.add_argument("--model", required=True)
        s.set_defaults(fn=fn)
    s = sub.add_parser("validate")
    s.add_argument("--model", required=True)
    s.add_argument("--validator", default="Iris Delgado")
    s.add_argument("--team", default="Independent Validation")
    s.set_defaults(fn=cmd_validate)
    s = sub.add_parser("monitor")
    s.add_argument("--model", required=True)
    s.add_argument("--shift", type=float, default=0.0)
    s.add_argument("--seed", type=int, default=101)
    s.set_defaults(fn=cmd_monitor)
    sub.add_parser("lifecycle").set_defaults(fn=cmd_lifecycle)
    s = sub.add_parser("gate")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_gate)
    s = sub.add_parser("regmap")
    s.add_argument("--framework")
    s.set_defaults(fn=cmd_regmap)
    s = sub.add_parser("portfolio")
    s.add_argument("--verify", action="store_true")
    s.set_defaults(fn=cmd_portfolio)
    s = sub.add_parser("agent")
    s.add_argument("--model", required=True)
    s.add_argument("--case", type=int, default=0)
    s.add_argument("--seed", type=int, default=7)
    s.add_argument("--untrusted")
    s.set_defaults(fn=cmd_agent)
    s = sub.add_parser("signoff")
    s.add_argument("action", choices=["request", "approve", "verify"])
    s.add_argument("--model")
    s.add_argument("--stage", default="production")
    s.add_argument("--role", default="model-risk")
    s.add_argument("--approver", default="")
    s.add_argument("--by", default="")
    s.add_argument("--comment", default="")
    s.add_argument("--reject", action="store_true")
    s.set_defaults(fn=cmd_signoff)
    s = sub.add_parser("telemetry")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_telemetry)
    s = sub.add_parser("iac")
    s.add_argument("--part", choices=["terraform", "bicep", "policies", "workbook", "workflows"], required=True)
    s.set_defaults(fn=cmd_iac)
    sub.add_parser("mcp").set_defaults(fn=cmd_mcp)
    sub.add_parser("mcp-demo").set_defaults(fn=cmd_mcp_demo)
    return p


def main(argv: list[str] | None = None) -> int:
    a = parser().parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
