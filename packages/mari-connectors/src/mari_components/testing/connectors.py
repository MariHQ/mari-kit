"""Storage-independent connector contract checks.

Applications can call this from their own fake-provider tests. It validates the
properties that are knowable from emitted pages; persistence crash tests remain
the application's responsibility because this package does not own storage.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable

from mari_components.sync import document_fingerprint
from mari_components.types import PollPage, SyncMode


@dataclass(frozen=True, slots=True)
class ConnectorContractReport:
    pages: int
    upserts: int
    tombstones: int
    final_cursor: str | None
    replay_fingerprint: str


def _poll_fingerprint(pages: tuple[PollPage, ...]) -> str:
    value = [{
        "upserts": [(document.external_id, document_fingerprint(document)) for document in page.upserts],
        "tombstones": [(item.external_id, item.reason) for item in page.tombstones],
        "cursor": page.next_cursor,
        "checkpoint": page.next_checkpoint,
        "complete": page.snapshot_complete,
        "metadata": dict(page.provider_metadata),
    } for page in pages]
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def check_connector_contract(
    pages: Iterable[PollPage],
    *,
    mode: SyncMode,
    starting_cursor: str | None = None,
) -> ConnectorContractReport:
    """Raise ``AssertionError`` when a connector violates shared page rules."""
    materialized = tuple(pages)
    assert materialized, "a poll must emit at least one page"
    seen_upserts: set[str] = set()
    seen_tombstones: set[str] = set()
    for index, page in enumerate(materialized):
        upsert_ids = [document.external_id for document in page.upserts]
        tombstone_ids = [tombstone.external_id for tombstone in page.tombstones]
        assert len(upsert_ids) == len(set(upsert_ids)), f"page {index} has duplicate upsert ids"
        assert len(tombstone_ids) == len(set(tombstone_ids)), f"page {index} has duplicate tombstones"
        assert not set(upsert_ids) & set(tombstone_ids), f"page {index} upserts and deletes the same id"
        seen_upserts.update(upsert_ids)
        seen_tombstones.update(tombstone_ids)
        if not page.snapshot_complete:
            assert page.next_cursor in {None, starting_cursor}, (
                f"incomplete page {index} advanced its durable cursor"
            )
        if mode is SyncMode.INCREMENTAL:
            assert not page.provider_metadata.get("absence_deletions"), (
                "incremental polls cannot request absence reconciliation"
            )
    final = materialized[-1]
    return ConnectorContractReport(
        pages=len(materialized),
        upserts=len(seen_upserts),
        tombstones=len(seen_tombstones),
        final_cursor=final.next_cursor,
        replay_fingerprint=_poll_fingerprint(materialized),
    )
