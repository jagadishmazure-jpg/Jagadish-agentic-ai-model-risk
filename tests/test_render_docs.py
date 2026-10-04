"""The doc renderer: output blocks and code excerpts."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("render_docs", ROOT / "scripts/render_docs.py")
rd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rd)


def test_output_block_is_filled_from_the_cli():
    out = rd.render("<!-- output: lifecycle -->\nstale\n<!-- /output -->\n")
    assert "cedarhollow-underwriting-assistant" in out and "stale" not in out


def test_python_excerpt_is_the_current_function():
    lang, body = rd.excerpt("src/modelrisk/scoring.py::score_risk")
    assert lang == "python" and body.startswith("def score_risk")


def test_constant_excerpt():
    _, body = rd.excerpt("src/modelrisk/lifecycle.py::REQUIRED_ROLES")
    assert body.startswith("REQUIRED_ROLES")


def test_decorated_function_excerpt_includes_the_decorator():
    _, body = rd.excerpt("src/modelrisk/gate.py::validation_outcome")
    assert body.startswith("@cache")


def test_hcl_block_excerpt_balances_braces():
    lang, body = rd.excerpt('infra/terraform/main.tf::resource "azurerm_storage_account"')
    assert lang == "hcl" and body.count("{") == body.count("}")


def test_bicep_block_excerpt():
    lang, body = rd.excerpt("infra/bicep/modules/registry.bicep::resource appi")
    assert lang == "bicep" and body.rstrip().endswith("}")


def test_unknown_name_fails():
    with pytest.raises(SystemExit):
        rd.excerpt("src/modelrisk/scoring.py::nope")


def test_failing_command_fails_the_render():
    with pytest.raises(SystemExit):
        rd.run("validate --model halcyon-fraud-triage --team 'Fraud Data Science team'")
