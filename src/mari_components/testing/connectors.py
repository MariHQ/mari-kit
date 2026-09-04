"""Storage-independent connector contract checks.

Applications can call this from their own fake-provider tests. It validates the
properties that are knowable from emitted pages; persistence crash tests remain
the application's responsibility because this package does not own storage.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

from mari_components.connectors.protocol import StreamEvent, VerifyStreamEvent
from mari_components.connectors.streaming import HydrateChange, stream_pages
from mari_components.json import canonical_json_bytes
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
    value = [
        {
            "upserts": [
                (document.document_id, document_fingerprint(document))
                for document in page.upserts
            ],
            "tombstones": [(item.document_id, item.reason) for item in page.tombstones],
            "cursor": page.next_cursor,
            "checkpoint": page.next_checkpoint,
            "complete": page.snapshot_complete,
            "metadata": dict(page.provider_metadata),
        }
        for page in pages
    ]
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


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
        upsert_ids = [document.document_id for document in page.upserts]
        tombstone_ids = [tombstone.document_id for tombstone in page.tombstones]
        assert len(upsert_ids) == len(set(upsert_ids)), (
            f"page {index} has duplicate upsert ids"
        )
        assert len(tombstone_ids) == len(set(tombstone_ids)), (
            f"page {index} has duplicate tombstones"
        )
        assert not set(upsert_ids) & set(tombstone_ids), (
            f"page {index} upserts and deletes the same id"
        )
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


def check_streaming_connector_contract(
    events: Iterable[StreamEvent],
    *,
    verify: VerifyStreamEvent,
    hydrate: HydrateChange,
) -> ConnectorContractReport:
    """Check deterministic stream parsing, hydration, and incremental pages.

    This helper runs fake events twice. Downstream contract tests should inject
    side-effect-free verification and hydration fixtures.
    """
    materialized = tuple(events)
    first = tuple(stream_pages(materialized, verify=verify, hydrate=hydrate))
    second = tuple(stream_pages(materialized, verify=verify, hydrate=hydrate))
    first_report = check_connector_contract(first, mode=SyncMode.INCREMENTAL)
    second_report = check_connector_contract(second, mode=SyncMode.INCREMENTAL)
    assert first_report.replay_fingerprint == second_report.replay_fingerprint, (
        "stream replay emitted different canonical pages"
    )
    return first_report
