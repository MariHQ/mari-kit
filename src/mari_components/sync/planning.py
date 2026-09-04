"""Side-effect-free synchronization planning with replay-safe invariants."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import asdict, dataclass, field
from types import MappingProxyType

from mari_components.json import canonical_json_bytes
from mari_components.types import KnowledgeDocument, PollPage, SyncMode, Tombstone


@dataclass(frozen=True, slots=True, kw_only=True)
class ManifestEntry:
    fingerprint: str
    revision: str
    source_id: str
    external_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SyncState:
    source_id: str = ""
    configuration_fingerprint: str = ""
    cursor: str | None = None
    checkpoint: str | None = None
    manifest: Mapping[str, ManifestEntry] = field(default_factory=dict)
    full_seen: frozenset[str] = frozenset()
    active_mode: SyncMode | None = None
    generation: int = 0

    def __post_init__(self) -> None:
        if self.generation < 0:
            raise ValueError("sync generation cannot be negative")
        if self.active_mode is None and self.full_seen:
            raise ValueError("full_seen requires an active full snapshot")
        if self.active_mode is not SyncMode.FULL and self.full_seen:
            raise ValueError("full_seen is only valid during a full snapshot")
        object.__setattr__(self, "manifest", MappingProxyType(dict(self.manifest)))


@dataclass(frozen=True, slots=True, kw_only=True)
class SyncPlan:
    upserts: tuple[KnowledgeDocument, ...]
    deletes: tuple[Tombstone, ...]
    unchanged: tuple[str, ...]
    state: SyncState
    snapshot_complete: bool
    expected_generation: int
    warnings: tuple[str, ...] = ()


def document_fingerprint(document: KnowledgeDocument) -> str:
    payload = {
        "revision": document.revision,
        "provider_revision": document.provider_revision,
        "content_digest": document.content_digest,
        "title": document.title,
        "body": document.body,
        "updated_at": document.updated_at,
        "source_url": document.source_url,
        "acl": {
            "visibility": document.acl.visibility,
            "principals": [asdict(principal) for principal in document.acl.principals],
        },
        "metadata": dict(document.metadata),
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def plan_sync(
    state: SyncState,
    page: PollPage,
    *,
    source_id: str,
    mode: SyncMode,
    configuration_fingerprint: str = "",
) -> SyncPlan:
    """Plan one provider page without performing persistence or side effects.

    Intermediate pages set ``snapshot_complete=False`` and carry a checkpoint.
    Only a terminal authoritative full page may reconcile absence. Explicit
    tombstones remain authoritative in either mode.
    """
    source_id = source_id.strip()
    if not source_id:
        raise ValueError("source_id is required")
    if state.source_id and state.source_id != source_id:
        raise ValueError(
            f"sync state belongs to {state.source_id!r}, not {source_id!r}"
        )
    configuration_fingerprint = configuration_fingerprint.strip()
    if (
        state.configuration_fingerprint
        and state.configuration_fingerprint != configuration_fingerprint
    ):
        raise ValueError("connector configuration changed; start with a new sync state")
    if state.active_mode is not None and state.active_mode is not mode:
        raise ValueError(
            f"incomplete {state.active_mode.value} sync cannot resume as {mode.value}"
        )
    foreign = sorted(
        {
            item.source_id
            for item in (*page.upserts, *page.tombstones)
            if item.source_id != source_id
        }
    )
    if foreign:
        raise ValueError(f"poll page contains foreign sources: {foreign!r}")
    incoming_ids = [document.document_id for document in page.upserts]
    if len(set(incoming_ids)) != len(incoming_ids):
        raise ValueError("poll page contains duplicate document IDs")
    tombstone_ids = [item.document_id for item in page.tombstones]
    if len(set(tombstone_ids)) != len(tombstone_ids):
        raise ValueError("poll page contains duplicate tombstones")
    overlap = set(incoming_ids) & set(tombstone_ids)
    if overlap:
        raise ValueError(f"poll page both upserts and deletes: {sorted(overlap)!r}")

    manifest = dict(state.manifest)
    seen = set(state.full_seen if mode is SyncMode.FULL else ())
    changed: list[KnowledgeDocument] = []
    unchanged: list[str] = []
    for document in page.upserts:
        fingerprint = document_fingerprint(document)
        prior = manifest.get(document.document_id)
        if prior is not None and prior.fingerprint == fingerprint:
            unchanged.append(document.document_id)
        else:
            changed.append(document)
            manifest[document.document_id] = ManifestEntry(
                fingerprint=fingerprint,
                revision=document.revision,
                source_id=document.source_id,
                external_id=document.external_id,
            )
        seen.add(document.document_id)

    deleted: dict[str, Tombstone] = {item.document_id: item for item in page.tombstones}
    for document_id in deleted:
        manifest.pop(document_id, None)
        seen.discard(document_id)

    if mode is SyncMode.FULL and page.snapshot_complete:
        for document_id in set(manifest) - seen:
            entry = manifest[document_id]
            deleted.setdefault(
                document_id,
                Tombstone(
                    source_id=entry.source_id,
                    external_id=entry.external_id,
                    reason="absent_from_complete_snapshot",
                ),
            )
        for document_id in deleted:
            manifest.pop(document_id, None)
        seen.clear()

    next_cursor = page.next_cursor if page.snapshot_complete else state.cursor
    next_checkpoint = None if page.snapshot_complete else page.next_checkpoint
    warnings = (
        ()
        if page.snapshot_complete
        else (
            "Snapshot is incomplete; cursor was held and absence was not treated as deletion.",
        )
    )
    next_state = SyncState(
        source_id=source_id,
        configuration_fingerprint=configuration_fingerprint,
        cursor=next_cursor,
        checkpoint=next_checkpoint,
        manifest=manifest,
        full_seen=frozenset(seen if mode is SyncMode.FULL else ()),
        active_mode=None if page.snapshot_complete else mode,
        generation=state.generation + 1,
    )
    return SyncPlan(
        upserts=tuple(changed),
        deletes=tuple(deleted[key] for key in sorted(deleted)),
        unchanged=tuple(unchanged),
        state=next_state,
        snapshot_complete=page.snapshot_complete,
        expected_generation=state.generation,
        warnings=warnings,
    )


def stream_sync(
    pages: Iterable[PollPage],
    initial_state: SyncState,
    *,
    source_id: str,
    mode: SyncMode,
    configuration_fingerprint: str = "",
) -> Iterator[SyncPlan]:
    """Lazily plan connector pages while carrying reconciliation state forward."""
    state = initial_state
    terminal = False
    emitted = False
    for page in pages:
        emitted = True
        if terminal:
            raise ValueError("connector emitted a page after its terminal page")
        plan = plan_sync(
            state,
            page,
            source_id=source_id,
            mode=mode,
            configuration_fingerprint=configuration_fingerprint,
        )
        yield plan
        state = plan.state
        terminal = plan.snapshot_complete
    if not emitted:
        raise ValueError("connector emitted no polling pages")
