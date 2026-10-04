"""Lookup from model id to the agent spec that implements it."""

from modelrisk.agents import banking, healthcare, insurance, mortgage, retail

SPECS = {m.SPEC.id: m.SPEC for m in (banking, insurance, mortgage, healthcare, retail)}
MODULES = {m.SPEC.id: m for m in (banking, insurance, mortgage, healthcare, retail)}
