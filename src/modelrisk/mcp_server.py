"""Read-only MCP server over the risk register.

Tools (all ``readOnlyHint``): list_models, get_model, query_risks, risk_heatmap,
scenario_results, gate_status, regulatory_controls. There is no tool that signs, edits or
deletes anything: agents can ask about risk, only people can accept it.

    modelrisk mcp          # stdio transport, for an MCP client
    modelrisk mcp-demo     # scripted in-memory session
"""

from __future__ import annotations

from typing import Any

import yaml
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from modelrisk import REGULATORY
from modelrisk.combine import scenario_results as _scenario_results
from modelrisk.combine import update_residuals
from modelrisk.registry import load, load_all
from modelrisk.scoring import BAND_ORDER, heatmap, score_risk
from modelrisk.tiering import eu_ai_act_class, tier

RO = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)


def _models() -> list[dict[str, Any]]:
    return [
        {
            "id": r.id,
            "name": r.model_card["name"],
            "domain": r.model_card["domain"],
            "company": r.model_card["company"],
            "kind": r.kind,
            "stage": r.stage,
            "tier": tier(r.model_card),
            "eu_ai_act": eu_ai_act_class(r.model_card),
            "owner": r.model_card["owner"],
        }
        for r in load_all()
    ]


def query(model_id: str | None = None, min_band: str = "low", category: str | None = None, owner: str | None = None) -> list[dict[str, Any]]:
    rows = []
    for r in load_all():
        if model_id and r.id != model_id:
            continue
        for risk in r.risks():
            s = score_risk(risk)
            if BAND_ORDER.index(s["inherent_band"]) < BAND_ORDER.index(min_band):
                continue
            if category and risk["category"] != category:
                continue
            if owner and owner.lower() not in risk["owner"].lower():
                continue
            rows.append({"model": r.id, **s})
    return sorted(rows, key=lambda x: (-x["inherent"], x["id"]))


def build_server() -> MCPServer:
    server = MCPServer("model-risk-register")

    @server.tool(annotations=RO)
    def list_models() -> list[dict[str, Any]]:
        """Every model in the inventory with its stage, tier, EU AI Act class and owner."""
        return _models()

    @server.tool(annotations=RO)
    def get_model(model_id: str) -> dict[str, Any]:
        """The model card of one model, with computed tier and EU AI Act class."""
        r = load(model_id)
        return {**r.model_card, "stage": r.stage, "tier": tier(r.model_card), "eu_ai_act": eu_ai_act_class(r.model_card)}

    @server.tool(annotations=RO)
    def query_risks(
        model_id: str | None = None, min_band: str = "low", category: str | None = None, owner: str | None = None
    ) -> list[dict[str, Any]]:
        """Risks filtered by model, minimum inherent band (low|medium|high|critical), category and owner."""
        return query(model_id, min_band, category, owner)

    @server.tool(annotations=RO)
    def risk_heatmap(model_id: str | None = None) -> dict[str, Any]:
        """5x5 likelihood x impact counts (rows impact 5..1, columns likelihood 1..5)."""
        rows = query(model_id)
        return {"grid": heatmap(rows), "risks": len(rows)}

    @server.tool(annotations=RO)
    def scenario_results(model_id: str) -> list[dict[str, Any]]:
        """Scenario results with controls on, plus the residual risk they imply."""
        r = load(model_id)
        res = _scenario_results(r)
        residual = {x["id"]: x["residual"] for x in update_residuals(r, res)}
        return [{**x, "residual_after": {rid: residual.get(rid) for rid in x["risk_ids"]}} for x in res]

    @server.tool(annotations=RO)
    def gate_status() -> dict[str, Any]:
        """Run the CI gate and return pass/fail per model and the failing checks."""
        from modelrisk.gate import run_gate

        g = run_gate()
        return {
            "ok": g["ok"],
            "models": [{"model": m["model"], "ok": m["ok"], "failed": [c["gate"] for c in m["checks"] if not c["ok"]]} for m in g["models"]],
        }

    @server.tool(annotations=RO)
    def regulatory_controls(framework: str) -> dict[str, Any]:
        """Mapping for one framework id (csa-ai-mrm, nist-ai-rmf, eu-ai-act, sr-11-7, iso-42001, hipaa, fair-lending, insurance-ai)."""
        doc = yaml.safe_load((REGULATORY / "mapping.yaml").read_text())
        for f in doc["frameworks"]:
            if f["id"] == framework:
                return f
        return {"error": f"unknown framework {framework}", "known": [f["id"] for f in doc["frameworks"]]}

    return server


TOOL_NAMES = ["list_models", "get_model", "query_risks", "risk_heatmap", "scenario_results", "gate_status", "regulatory_controls"]


async def demo() -> list[str]:
    """Scripted session used by ``modelrisk mcp-demo``: what a governance agent would ask."""
    from mcp import Client

    lines = []
    async with Client(build_server()) as client:
        tools = await client.list_tools()
        lines.append("tools: " + ", ".join(sorted(t.name for t in tools.tools)))
        ro = all(t.annotations and t.annotations.read_only_hint for t in tools.tools)
        lines.append(f"all read-only: {ro}")
        res = await client.call_tool("query_risks", {"min_band": "critical"})
        rows = res.structured_content["result"]
        lines.append(f"critical inherent risks: {len(rows)}")
        for row in rows:
            lines.append(f"  {row['model']:<36} {row['id']:<8} inherent {row['inherent']:>2} -> residual {row['residual']}")
        res = await client.call_tool("scenario_results", {"model_id": "cedarhollow-underwriting-assistant"})
        for row in res.structured_content["result"]:
            if row["kind"] == "bias":
                lines.append(f"  {row['id']} {row['metric']} = {row['value']} ({row['status']})")
        res = await client.call_tool("regulatory_controls", {"framework": "nist-ai-rmf"})
        lines.append("nist-ai-rmf items: " + ", ".join(i["ref"] for i in res.structured_content["items"]))
    return lines
