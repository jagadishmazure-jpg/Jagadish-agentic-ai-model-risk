"""Human-in-the-loop sign-off with a hash-chained audit log.

* A sign-off is bound to the **digest** of the four pillar artifacts it approved. Change any
  card afterwards and the sign-off goes stale; the CI gate fails until someone signs again.
* No self sign-off: the approver cannot be the model's developer team, and a validator cannot
  be the model owner either.
* Sign-offs expire after ``MAX_AGE_DAYS`` (annual revalidation).
* Every request and decision is appended to ``registry/audit-log.jsonl``; each line carries the
  hash of the previous line, so editing or deleting history breaks ``verify_chain``.

There is deliberately no MCP tool for signing: agents can read the register, only people sign.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import yaml

from modelrisk import REGISTRY
from modelrisk.registry import FILES, PILLARS, ModelRecord, load

MAX_AGE_DAYS = 365
AUDIT_LOG = REGISTRY / "audit-log.jsonl"
GENESIS = "0" * 64


class SignoffRefused(Exception):
    pass


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def digest(rec: ModelRecord) -> str:
    """sha256 over the parsed content of the four pillars (comments and layout do not count)."""
    body = {p: getattr(rec, p) for p in PILLARS}
    return hashlib.sha256(canonical(body).encode()).hexdigest()


def read_log(path: Path = AUDIT_LOG) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def append(event: dict[str, Any], path: Path = AUDIT_LOG) -> dict[str, Any]:
    log = read_log(path)
    prev = log[-1]["hash"] if log else GENESIS
    entry = {"seq": len(log) + 1, **event, "prev": prev}
    entry["hash"] = hashlib.sha256((prev + canonical(entry)).encode()).hexdigest()
    with path.open("a") as f:
        f.write(canonical(entry) + "\n")
    return entry


def verify_chain(path: Path = AUDIT_LOG) -> dict[str, Any]:
    prev = GENESIS
    for i, e in enumerate(read_log(path), 1):
        body = {k: v for k, v in e.items() if k != "hash"}
        if e["prev"] != prev or e["seq"] != i:
            return {"ok": False, "broken_at": i, "reason": "sequence or previous-hash mismatch"}
        if hashlib.sha256((prev + canonical(body)).encode()).hexdigest() != e["hash"]:
            return {"ok": False, "broken_at": i, "reason": "entry hash mismatch"}
        prev = e["hash"]
    return {"ok": True, "entries": len(read_log(path))}


def request(rec: ModelRecord, stage: str, requested_by: str, now: int | None = None, log: Path = AUDIT_LOG) -> dict[str, Any]:
    return append(
        {
            "event": "signoff-requested",
            "model_id": rec.id,
            "stage": stage,
            "actor": requested_by,
            "digest": digest(rec),
            "epoch": int(now or time.time()),
        },
        log,
    )


def sign(
    rec: ModelRecord,
    stage: str,
    role: str,
    approver: str,
    decision: str,
    comment: str,
    now: int | None = None,
    log: Path = AUDIT_LOG,
    write: bool = True,
) -> dict[str, Any]:
    """Record a human decision. Raises ``SignoffRefused`` for self sign-off or an empty comment."""
    card = rec.model_card
    team = card["developer"].lower()
    if approver.lower() in team or team in approver.lower():
        raise SignoffRefused("approver belongs to the developer team (no self sign-off)")
    if role == "validator" and approver.split(" (")[0].lower() == card["owner"].split(" (")[0].lower():
        raise SignoffRefused("the model owner cannot act as independent validator")
    if decision not in ("approve", "reject"):
        raise SignoffRefused("decision must be approve or reject")
    if len(comment.strip()) < 10:
        raise SignoffRefused("a sign-off needs a written rationale")
    epoch = int(now or time.time())
    d = digest(rec)
    entry = append(
        {"event": "signoff", "model_id": rec.id, "stage": stage, "role": role, "actor": approver, "decision": decision, "digest": d, "epoch": epoch},
        log,
    )
    record = {
        "stage": stage,
        "role": role,
        "approver": approver,
        "decision": decision,
        "digest": d,
        "signed_epoch": epoch,
        "comment": comment,
        "audit_hash": entry["hash"],
    }
    if write:
        path = rec.folder / FILES["approvals"]
        doc = yaml.safe_load(path.read_text()) if path.exists() else {"model_id": rec.id, "signoffs": []}
        doc["signoffs"] = [s for s in doc["signoffs"] if not (s["stage"] == stage and s["role"] == role)] + [record]
        path.write_text(yaml.safe_dump(doc, sort_keys=False, width=100))
    return record


def valid_signoffs(rec: ModelRecord, stage: str, now: int | None = None) -> dict[str, dict[str, Any]]:
    """role -> sign-off, for approvals that match the current digest and have not expired."""
    now = int(now or time.time())
    d = digest(rec)
    log_hashes = {e["hash"] for e in read_log()}
    out = {}
    for s in (rec.approvals or {}).get("signoffs", []):
        fresh = now - s["signed_epoch"] <= MAX_AGE_DAYS * 86400
        if s["stage"] == stage and s["decision"] == "approve" and s["digest"] == d and fresh and s["audit_hash"] in log_hashes:
            out[s["role"]] = s
    return out


def stale_signoffs(rec: ModelRecord, now: int | None = None) -> list[str]:
    now = int(now or time.time())
    d = digest(rec)
    return [
        f"{s['stage']}/{s['role']}" + (" digest changed" if s["digest"] != d else " expired")
        for s in (rec.approvals or {}).get("signoffs", [])
        if s["digest"] != d or now - s["signed_epoch"] > MAX_AGE_DAYS * 86400
    ]


def reload(model_id: str) -> ModelRecord:
    return load(model_id)
