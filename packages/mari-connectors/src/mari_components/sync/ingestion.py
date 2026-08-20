"""Page-at-a-time connector ingestion over a caller-owned apply port."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from mari_components import PollPage, SyncMode
from mari_components.sync import SyncPlan, SyncState, plan_sync


@dataclass(frozen=True, slots=True)
class AppliedPage:
    inserted_ids: tuple[int, ...] = ()
    updated_ids: tuple[int, ...] = ()
    deleted: int = 0
    chunks: int = 0
    embeddings: int = 0


@dataclass(frozen=True, slots=True)
class IngestionReport:
    state: SyncState
    pages: int
    changed: int
    unchanged: int
    deleted: int
    chunks: int
    embeddings: int
    inserted_ids: tuple[int, ...]
    updated_ids: tuple[int, ...]
    snapshot_complete: bool


ApplyPage = Callable[[SyncPlan, int], AppliedPage]


def consume_connector_pages(
    pages: Iterable[PollPage],
    initial_state: SyncState,
    mode: SyncMode,
    *,
    apply_page: ApplyPage,
) -> IngestionReport:
    """Plan and transactionally apply provider pages without buffering them.

    ``apply_page`` must commit the document changes and ``plan.state`` in the
    same transaction. If it fails, iteration stops and that provider page is
    replayed from the prior durable checkpoint on the next attempt.
    """
    state = initial_state
    page_count = changed = unchanged = deleted = chunks = embeddings = 0
    inserted_ids: list[int] = []
    updated_ids: list[int] = []
    complete = False
    for page_count, page in enumerate(pages, start=1):
        if complete:
            raise ValueError("connector emitted a page after its terminal page")
        plan = plan_sync(state, page, mode=mode)
        applied = apply_page(plan, page_count)
        state = plan.state
        complete = plan.snapshot_complete
        changed += len(plan.upserts)
        unchanged += len(plan.unchanged)
        deleted += applied.deleted
        chunks += applied.chunks
        embeddings += applied.embeddings
        inserted_ids.extend(applied.inserted_ids)
        updated_ids.extend(applied.updated_ids)
    if page_count == 0:
        raise ValueError("connector emitted no polling pages")
    return IngestionReport(
        state, page_count, changed, unchanged, deleted, chunks, embeddings,
        tuple(inserted_ids), tuple(updated_ids), complete,
    )
