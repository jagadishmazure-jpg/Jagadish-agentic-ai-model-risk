# Contributing

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Before opening a pull request

```bash
ruff check . && ruff format --check .
pytest -q
modelrisk gate
python scripts/render_docs.py --check
```

If you change a pillar (anything under `registry/<model-id>/`), the digest changes and the sign-offs go
stale, so `modelrisk gate` fails at G7 until people re-approve. In this demo repository, run
`python scripts/seed_signoffs.py` to regenerate the fictional sign-offs, then
`python scripts/render_docs.py` to refresh pasted outputs.

## Rules

- Fictional companies and synthetic data only. No real client names, people or identifiers.
- Paraphrase and attribute third-party frameworks; never copy their text. The CSA framework PDF must
  never be committed (`*.pdf` is ignored and a test checks it). Run
  `python scripts/overlap_check.py <reference texts>` on new prose; it must report 0 overlaps.
- New scenario families need a runner, a runtime control, risk-card links and a doc with all 16 sections.
- No dates in docs, no unfinished placeholders, and a README with a file table in every folder.
- Terraform and Bicep stay equivalent and load the same policy JSON.
