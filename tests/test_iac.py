"""Infrastructure and workflow structure, checked offline (no Terraform or Bicep binaries needed)."""

import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
POL = ROOT / "infra/policies"
WF = ROOT / ".github/workflows"
TF = ROOT / "infra/terraform"
POLICIES = ["require-model-card-tags", "allowed-risk-tier", "deny-public-ai-endpoints"]


@pytest.mark.parametrize("name", POLICIES)
def test_policy_definition_shape(name):
    d = json.loads((POL / f"{name}.json").read_text())
    assert d["mode"] == "Indexed" and {"if", "then"} <= set(d["policyRule"])
    assert d["policyRule"]["then"]["effect"] == "[parameters('effect')]"
    eff = d["parameters"]["effect"]
    assert set(eff["allowedValues"]) >= {"Audit", "Deny"} and eff["defaultValue"] in eff["allowedValues"]


def test_model_card_tag_policy_requires_the_card_fields():
    d = json.loads((POL / "require-model-card-tags.json").read_text())
    assert d["parameters"]["tagNames"]["defaultValue"] == ["model-id", "model-owner", "risk-tier", "model-card-uri"]
    assert "Microsoft.CognitiveServices/accounts" in d["parameters"]["aiResourceTypes"]["defaultValue"]


def test_risk_tier_values_match_the_inventory_tiers():
    from modelrisk.lifecycle import REQUIRED_ROLES

    d = json.loads((POL / "allowed-risk-tier.json").read_text())
    assert d["parameters"]["allowedTiers"]["defaultValue"] == [str(t) for t in sorted(REQUIRED_ROLES["production"])]


def test_terraform_and_bicep_load_the_same_policy_files():
    tf = (TF / "locals.tf").read_text()
    bicep = (ROOT / "infra/bicep/modules/policies.bicep").read_text()
    for p in POL.glob("*.json"):
        assert p.name in tf and p.name in bicep


def test_both_stacks_load_the_same_workbook():
    assert "model-risk-workbook.json" in (TF / "main.tf").read_text()
    assert "model-risk-workbook.json" in (ROOT / "infra/bicep/modules/registry.bicep").read_text()


def test_workbook_queries_the_emitted_event_names():
    wb = (ROOT / "infra/workbook/model-risk-workbook.json").read_text()
    for name in ("modelrisk.gate", "modelrisk.scenario", "modelrisk.drift", "modelrisk.residual", "modelrisk.signoff"):
        assert name in wb


def test_smallest_settings():
    main = (TF / "main.tf").read_text()
    assert '"PerGB2018"' in main and '"LRS"' in main
    variables = (TF / "variables.tf").read_text()
    assert re.search(r'variable "log_retention_days"[\s\S]*?default\s*=\s*30', variables)
    assert re.search(r'variable "deploy_drift_alert"[\s\S]*?default\s*=\s*false', variables)
    params = json.loads((ROOT / "infra/bicep/main.parameters.json").read_text())["parameters"]
    assert params["deployDriftAlert"]["value"] is False


def test_evidence_registry_is_keyless_and_versioned():
    main = (TF / "main.tf").read_text()
    assert "shared_access_key_enabled       = false" in main and "versioning_enabled = true" in main
    bicep = (ROOT / "infra/bicep/modules/registry.bicep").read_text()
    assert "allowSharedKeyAccess: false" in bicep and "isVersioningEnabled: true" in bicep


def test_app_insights_disables_local_auth_in_both_stacks():
    assert re.search(r"local_authentication_enabled\s*=\s*false", (TF / "main.tf").read_text())
    assert "DisableLocalAuth: true" in (ROOT / "infra/bicep/modules/registry.bicep").read_text()


def test_dev_audits_and_prod_denies():
    assert 'policy_effect      = "Audit"' in (TF / "envs/dev.tfvars").read_text()
    assert 'policy_effect      = "Deny"' in (TF / "envs/prod.tfvars").read_text()


def test_checkov_skips_are_all_justified():
    lines = (ROOT / ".checkov.yaml").read_text().splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("- CKV"):
            assert lines[i - 1].strip().startswith("#"), line


def wf(name):
    return yaml.safe_load((WF / name).read_text())


def test_workflows_exist_and_parse():
    for n in ("ci.yml", "infra.yml", "deploy.yml", "teardown.yml"):
        assert isinstance(wf(n), dict)


def test_ci_runs_tests_gate_and_doc_drift_check():
    text = (WF / "ci.yml").read_text()
    assert "pytest -q" in text and "modelrisk gate" in text and "render_docs.py --check" in text


def test_deploy_is_gated_and_uses_oidc():
    d = wf("deploy.yml")
    jobs = d["jobs"]
    for name in ("deploy-dev", "deploy-prod"):
        assert "vars.DEPLOY_ENABLED == 'true'" in jobs[name]["if"]
        assert jobs[name]["permissions"]["id-token"] == "write"
        assert any("azure/login" in s.get("uses", "") for s in jobs[name]["steps"])
    assert jobs["deploy-dev"]["environment"] == "dev" and jobs["deploy-prod"]["environment"] == "prod"
    assert jobs["deploy-prod"]["needs"] == "deploy-dev"
    on = d[True] if True in d else d["on"]
    assert on["workflow_dispatch"]["inputs"]["deploy_tool"]["options"] == ["terraform", "bicep"]
    text = (WF / "deploy.yml").read_text()
    assert "client-secret" not in text and "AZURE_CLIENT_SECRET" not in text


def test_teardown_needs_gate_and_confirmation():
    job = wf("teardown.yml")["jobs"]["teardown"]
    assert "vars.DEPLOY_ENABLED == 'true'" in job["if"] and "inputs.confirm == inputs.environment" in job["if"]


def test_deploy_script_has_every_subcommand():
    text = (ROOT / ".github/scripts/deploy.sh").read_text()
    for fn in ("provision()", "smoke()", "publish()", "destroy()"):
        assert fn in text
    assert "--auth-mode login" in text


def test_terraform_tests_cover_dev_and_prod():
    t = (TF / "tests/plan.tftest.hcl").read_text()
    assert 'run "dev_evidence_plane"' in t and 'run "prod_denies_and_alerts"' in t and 'mock_provider "azurerm"' in t


def test_iac_summary_command_reads_the_files():
    from modelrisk.iac import PARTS

    assert any("azurerm_application_insights_workbook" in line for line in PARTS["terraform"]())
    assert any("Microsoft.Insights/workbooks" in line for line in PARTS["bicep"]())
    assert len(PARTS["workbook"]()) == 5


def test_workflows_are_hardened():
    """Supply-chain guard: every third-party action is pinned to a full commit SHA with a version
    comment, every workflow sets top-level permissions, CI runs gitleaks, and CodeQL and Dependabot
    are configured. Dependabot bumps keep the SHA and the comment together, so this stays green."""
    wf_dir = ROOT / ".github" / "workflows"
    for f in sorted(wf_dir.glob("*.yml")):
        text = f.read_text()
        assert re.search(r"^permissions:", text, re.M), f"{f.name}: no top-level permissions"
        for line in text.splitlines():
            m = re.search(r"\buses:\s*([^\s#]+)\s*(#.*)?$", line)
            if m and not m.group(1).startswith("./"):
                assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", m.group(1)), f"{f.name}: {line.strip()}"
                assert m.group(2) and re.match(r"#\s*v\d", m.group(2)), f"{f.name}: no version comment"
    assert "gitleaks/gitleaks-action@" in (wf_dir / "ci.yml").read_text()
    assert "github/codeql-action/analyze@" in (wf_dir / "codeql.yml").read_text()
    deps = (ROOT / ".github" / "dependabot.yml").read_text()
    assert "package-ecosystem: github-actions" in deps and "interval: weekly" in deps
