"""Read-only summaries of the IaC and workflows, parsed from the files in this repository.

``modelrisk iac --part terraform|bicep|policies|workbook|workflows`` prints them; the infra
docs paste that output, so a change to main.tf or a workflow shows up as a stale doc in CI.
"""

from __future__ import annotations

import json
import re

import yaml

from modelrisk import ROOT

INFRA = ROOT / "infra"


def terraform() -> list[str]:
    main = (INFRA / "terraform/main.tf").read_text()
    out = [f"resource  {t:<48} {n}" for t, n in re.findall(r'^resource "([^"]+)" "([^"]+)"', main, re.M)]
    variables = re.findall(r'^variable "([^"]+)"', (INFRA / "terraform/variables.tf").read_text(), re.M)
    outputs = re.findall(r'^output "([^"]+)"', (INFRA / "terraform/outputs.tf").read_text(), re.M)
    tests = re.findall(r'^run "([^"]+)"', (INFRA / "terraform/tests/plan.tftest.hcl").read_text(), re.M)
    return [*out, f"variables {', '.join(variables)}", f"outputs   {', '.join(outputs)}", f"tests     {', '.join(tests)}"]


def bicep() -> list[str]:
    out = []
    for f in ["main.bicep", "modules/policies.bicep", "modules/registry.bicep"]:
        text = (INFRA / "bicep" / f).read_text()
        for name, typ in re.findall(r"^resource (\w+) '([^@']+)@", text, re.M):
            out.append(f"{f:<24} {name:<14} {typ}")
        for name in re.findall(r"^module (\w+) ", text, re.M):
            out.append(f"{f:<24} {name:<14} (module)")
    return out


def policies() -> list[str]:
    out = []
    for p in sorted((INFRA / "policies").glob("*.json")):
        d = json.loads(p.read_text())
        params = d["parameters"]
        extra = ""
        if "tagNames" in params:
            extra = " tags=" + ",".join(params["tagNames"]["defaultValue"])
        if "allowedTiers" in params:
            extra = " tiers=" + ",".join(params["allowedTiers"]["defaultValue"])
        out.append(f"{p.stem:<26} mode={d['mode']:<8} default={params['effect']['defaultValue']}{extra}")
    for env in ("dev", "prod"):
        tfvars = (INFRA / f"terraform/envs/{env}.tfvars").read_text()
        effect = re.search(r'policy_effect\s*=\s*"(\w+)"', tfvars).group(1)
        out.append(f"assigned effect in {env}: {effect}")
    return out


def workbook() -> list[str]:
    d = json.loads((INFRA / "workbook/model-risk-workbook.json").read_text())
    out = []
    for item in d["items"]:
        c = item["content"]
        if "query" in c:
            event = re.search(r"name == '([^']+)'", c["query"]).group(1)
            out.append(f"{c['title']:<32} {event:<20} {c['visualization']}")
    return out


def workflows() -> list[str]:
    out = []
    for f in sorted((ROOT / ".github/workflows").glob("*.yml")):
        d = yaml.safe_load(f.read_text())
        on = d.get(True, d.get("on"))
        triggers = ",".join(on) if isinstance(on, dict) else str(on)
        for job, spec in d["jobs"].items():
            gate = "DEPLOY_ENABLED" if "DEPLOY_ENABLED" in str(spec.get("if", "")) else "-"
            env = spec.get("environment", "-")
            oidc = "oidc" if spec.get("permissions", {}).get("id-token") == "write" else "-"
            out.append(f"{f.name:<14} {job:<12} on={triggers:<34} gate={gate:<15} env={env!s:<26} {oidc}")
    return out


PARTS = {"terraform": terraform, "bicep": bicep, "policies": policies, "workbook": workbook, "workflows": workflows}
