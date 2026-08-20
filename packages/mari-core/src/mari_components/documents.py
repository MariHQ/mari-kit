"""Storage-neutral knowledge-document identity and lifecycle values."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Any


def document_key(project_id: int, source_id: str, external_id: str) -> str:
    return hashlib.sha256(f"{project_id}\0{source_id}\0{external_id}".encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class DocumentVersion:
    project_id: int
    source_id: str
    external_id: str
    revision: str
    title: str
    body: str
    status: str = "active"
    source_url: str = ""
    acl: dict[str, Any] = field(default_factory=lambda: {"visibility": "project", "principals": []})
    reason: str = "connector poll"
    actor: str = "connector"
    version_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    recorded_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))

    def __post_init__(self) -> None:
        if self.project_id <= 0 or not self.source_id or not self.external_id:
            raise ValueError("document versions require project, source, and external ids")
        if self.status not in {"active", "archived", "deleted"}:
            raise ValueError("invalid document lifecycle status")
        if self.recorded_at.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.body.encode()).hexdigest()

    @property
    def acl_json(self) -> str:
        return json.dumps(self.acl, sort_keys=True, separators=(",", ":"))
