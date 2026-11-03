"""AI model risk management as code (model cards, data sheets, risk cards and scenario planning).

Paths and constants shared by every module. All companies, people and data are fictional.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "registry"
SCHEMAS = ROOT / "schemas"
REGULATORY = ROOT / "regulatory"
EVIDENCE = ROOT / "evidence"
SEED = 7
