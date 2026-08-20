"""Storage-neutral tamper-evident audit values and hash-chain rules."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import typing as t
import uuid
from dataclasses import asdict, dataclass, field


_SENSITIVE = re.compile(r"token|secret|password|authorization|cookie|api[_-]?key", re.I)


def redact(value: t.Any) -> t.Any:
    if isinstance(value, dict):
        return {str(key): ("[REDACTED]" if _SENSITIVE.search(str(key)) else redact(item))
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class AuditEvent:
    project_id: int
    actor_type: str
    actor_id: str
    actor_name: str
    action: str
    resource_type: str
    resource_id: str
    outcome: str = "success"
    reason: str = ""
    request_id: str = ""
    correlation_id: str = ""
    detail: dict[str, t.Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))

    def __post_init__(self) -> None:
        if self.project_id < 0:
            raise ValueError("project_id cannot be negative")
        if self.outcome not in {"success", "failure", "denied", "manual"}:
            raise ValueError("invalid audit outcome")
        if not self.action or not self.resource_type:
            raise ValueError("audit action and resource type are required")


def _canonical(row: dict[str, t.Any]) -> bytes:
    serializable = dict(row)
    when = serializable.get("occurred_at")
    if isinstance(when, dt.datetime):
        serializable["occurred_at"] = when.astimezone(dt.timezone.utc).isoformat()
    return json.dumps(serializable, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def chained_row(event: AuditEvent, previous_hash: str) -> dict[str, t.Any]:
    row = asdict(event)
    row["detail_json"] = json.dumps(
        redact(row.pop("detail")), sort_keys=True, separators=(",", ":"), default=str,
    )
    row["previous_hash"] = previous_hash
    row["event_hash"] = hashlib.sha256(previous_hash.encode() + _canonical(row)).hexdigest()
    return row


def verify_chain(rows: list[dict[str, t.Any]]) -> bool:
    previous_by_project: dict[int, str] = {}
    for original in sorted(rows, key=lambda row: (row["occurred_at"], row["event_id"])):
        row = dict(original)
        actual = row.pop("event_hash")
        project_id = int(row["project_id"])
        previous = previous_by_project.get(project_id, "")
        if row.get("previous_hash") != previous:
            return False
        if hashlib.sha256(previous.encode() + _canonical(row)).hexdigest() != actual:
            return False
        previous_by_project[project_id] = actual
    return True
