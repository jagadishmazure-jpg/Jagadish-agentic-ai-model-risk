"""Rebuild the checked-in sign-offs and audit log from the current pillar artifacts.

Run this after changing any pillar artifact, the same way a real change would go back through
review: every sign-off is re-recorded against the new digest. The identities are fictional.
The two models in validation are left one sign-off short of production on purpose, so the
lifecycle report shows a real blocker.

    python scripts/seed_signoffs.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from modelrisk.lifecycle import STAGES, required_roles
from modelrisk.registry import FILES, load, load_all
from modelrisk.signoff import AUDIT_LOG, request, sign

PEOPLE = {
    "validator": "Iris Delgado (Independent Validation)",
    "model-risk": "Marcus Feld (Model Risk Management)",
    "compliance": "Grace Liang (Compliance)",
    "privacy": "Sam Whitlock (Privacy Office)",
    "clinical-reviewer": "Dr. Amara Quist (Clinical Review)",
}
BUSINESS = {
    "halcyon-fraud-triage": "Elena Ruiz (Head of Card Services)",
    "bramblewood-claims-triage": "Victor Hale (Personal Lines Claims)",
    "cedarhollow-underwriting-assistant": "Dana Whitfield (Head of Mortgage Operations)",
    "juniper-prior-auth": "Priya Natarajan (Utilization Management Operations)",
    "marigold-pricing-demand": "Ben Okoro (Category Management)",
}
WITHHELD = {"cedarhollow-underwriting-assistant": {"compliance"}, "juniper-prior-auth": {"compliance", "clinical-reviewer"}}


def who(rec, role: str) -> str:
    if role == "model-owner":
        return rec.model_card["owner"]
    if role == "business-owner":
        return BUSINESS.get(rec.id, rec.model_card["owner"])
    return PEOPLE[role]


def main() -> None:
    now = int(time.time())
    AUDIT_LOG.write_text("")
    for rec in load_all():
        (rec.folder / FILES["approvals"]).unlink(missing_ok=True)
    for rec in load_all():
        idx = STAGES.index(rec.stage)
        stages = [s for s in STAGES[1 : idx + 1] if s != "retired"]
        if rec.stage == "validation":
            stages.append("production")
        if not stages:
            request(rec, "validation", rec.model_card["owner"], now)
        for stage in stages:
            request(rec, stage, rec.model_card["owner"], now)
            for role in required_roles(rec, stage):
                if stage == "production" and rec.stage == "validation" and role in WITHHELD.get(rec.id, set()):
                    continue
                sign(
                    load(rec.id),
                    stage,
                    role,
                    who(rec, role),
                    "approve",
                    f"Reviewed the {stage} evidence pack for {rec.id}: pillars, scenarios and validation report.",
                    now,
                )
    print(f"seeded sign-offs for {len(load_all())} models; audit log {sum(1 for _ in AUDIT_LOG.open())} entries")


if __name__ == "__main__":
    main()
