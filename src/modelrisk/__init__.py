"""AI model risk management as code (CSA AI MRM pillars, implemented in my own design).

Paths and constants shared by every module. All companies, people and data are fictional.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "registry"
SCHEMAS = ROOT / "schemas"
REGULATORY = ROOT / "regulatory"
EVIDENCE = ROOT / "evidence"
SEED = 7
