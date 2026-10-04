"""Shared fixtures. Everything is offline: mock agents, synthetic data, no Azure."""

from __future__ import annotations

import copy

import pytest

from modelrisk.registry import load, load_all

DOMAIN_IDS = ["halcyon-fraud-triage", "bramblewood-claims-triage", "cedarhollow-underwriting-assistant",
              "juniper-prior-auth", "marigold-pricing-demand"]
PORTFOLIO_IDS = ["pfa-mortgage-flow", "pfs-safety-layer", "pal-agent-labs", "pfb-fabric-data-agent", "pff-finops-agent"]
ALL_IDS = DOMAIN_IDS + PORTFOLIO_IDS


@pytest.fixture(scope="session")
def records():
    return {r.id: r for r in load_all()}


@pytest.fixture
def fresh():
    """A deep copy of one record that a test may mutate in memory."""
    return lambda model_id: copy.deepcopy(load(model_id))


@pytest.fixture(scope="session")
def gate():
    from modelrisk.gate import run_gate

    return run_gate()
