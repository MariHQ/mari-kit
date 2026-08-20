"""Side-effect-free synchronization planning with replay-safe invariants."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from types import MappingProxyType
from typing import Mapping

from mari_components.types import KnowledgeDocument, PollPage, SyncMode, Tombstone


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    fingerprint: str
    revision: str = ""


@dataclass(frozen=True, slots=True)
class SyncState:
    cursor: str | None = None
    checkpoint: str | None = None
    manifest: Mapping[str, ManifestEntry] = field(default_factory=dict)
    full_seen: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest", MappingProxyType(dict(self.manifest)))


@dataclass(frozen=True, slots=True)
class SyncPlan:
    upserts: tuple[KnowledgeDocument, ...]
    deletes: tuple[Tombstone, ...]
    unchanged: tuple[str, ...]
    state: SyncState
    snapshot_complete: bool
    warnings: tuple[str, ...] = ()


def document_fingerprint(document: KnowledgeDocument) -> str:
    payload = {
        "revision": document.revision,
        "title": document.title,
        "body": document.body,
        "source_url": document.source_url,
        "acl": {
            "visibility": document.acl.visibility,
            "principals": [asdict(principal) for principal in document.acl.principals],
        },
        "metadata": dict(document.metadata),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def plan_sync(state: SyncState, page: PollPage, *, mode: SyncMode) -> SyncPlan:
    """Plan one provider page without performing persistence or side effects.

    Intermediate pages set ``snapshot_complete=False`` and carry a checkpoint.
    Only a terminal authoritative full page may reconcile absence. Explicit
    tombstones remain authoritative in either mode.
    """
    incoming_ids = [document.external_id for document in page.upserts]
    if len(set(incoming_ids)) != len(incoming_ids):
        raise ValueError("poll page contains duplicate document IDs")
    tombstone_ids = [item.external_id for item in page.tombstones]
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
        prior = manifest.get(document.external_id)
        if document.metadata.get("unchanged") is True and prior is not None:
            unchanged.append(document.external_id)
        elif prior is not None and prior.fingerprint == fingerprint:
            unchanged.append(document.external_id)
        else:
            changed.append(document)
            manifest[document.external_id] = ManifestEntry(fingerprint, document.revision)
        seen.add(document.external_id)

    deleted: dict[str, Tombstone] = {item.external_id: item for item in page.tombstones}
    for external_id in deleted:
        manifest.pop(external_id, None)
        seen.discard(external_id)

    if mode is SyncMode.FULL and page.snapshot_complete:
        for external_id in set(manifest) - seen:
            deleted.setdefault(external_id, Tombstone(external_id, "absent_from_complete_snapshot"))
        for external_id in deleted:
            manifest.pop(external_id, None)
        seen.clear()

    next_cursor = page.next_cursor if page.snapshot_complete else state.cursor
    next_checkpoint = None if page.snapshot_complete else page.next_checkpoint
    warnings = () if page.snapshot_complete else (
        "Snapshot is incomplete; cursor was held and absence was not treated as deletion.",
    )
    next_state = SyncState(
        cursor=next_cursor,
        checkpoint=next_checkpoint,
        manifest=manifest,
        full_seen=frozenset(seen if mode is SyncMode.FULL else ()),
    )
    return SyncPlan(
        tuple(changed),
        tuple(deleted[key] for key in sorted(deleted)),
        tuple(unchanged),
        next_state,
        page.snapshot_complete,
        warnings,
    )
