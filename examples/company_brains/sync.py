"""Continuously synchronize a paginated company brain with the sync planner.

The module keeps the provider, planner, and persistence boundaries separate:

* ``CompanySource`` is a credential-free provider boundary that emits canonical
  ``PollPage`` values, including paginated full snapshots and tombstones.
* ``plan_sync`` / ``stream_sync`` compute document changes with no side effects.
* ``CompanyBrain`` is the host application. It persists canonical revisions to
  the public ``InMemoryDocumentStore``, keeps a live projection, and advances
  ``SyncState`` only through ``apply_sync_plan`` so every write is guarded by
  the optimistic generation check exposed by the application API.

Only the terminal page of a full snapshot may reconcile absence, an incomplete
full snapshot mode-locks the state until it completes, tombstones are
authoritative in any mode, and concurrent plans from one generation cannot both
commit. The host owns atomic persistence and authorization; Mari supplies the
planner, the generation contract, and reference store semantics.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence

from mari_kit import (
    DocumentACL,
    KnowledgeDocument,
    PollPage,
    Principal,
    ScopeRef,
    SyncMode,
    Tombstone,
    canonical_document_id,
)
from mari_kit.platform import InMemoryDocumentStore
from mari_kit.sync import (
    SyncPlan,
    SyncState,
    apply_sync_plan,
    plan_sync,
    stream_sync,
)

SOURCE_ID = "handbook:acme"
SCOPE = ScopeRef(tenant="acme", space="handbook")


def company_document(
    external_id: str,
    body: str,
    revision: str,
    *,
    visibility: str = "connector_scope",
    principals: Sequence[Principal] = (),
) -> KnowledgeDocument:
    """Build one provider revision with a stable title and observed ACL."""

    return KnowledgeDocument(
        source_id=SOURCE_ID,
        external_id=external_id,
        title=external_id.rsplit("/", 1)[-1].replace("-", " ").title(),
        body=body,
        revision=revision,
        acl=DocumentACL(visibility=visibility, principals=tuple(principals)),
    )


def initial_documents() -> tuple[KnowledgeDocument, ...]:
    return (
        company_document(
            "policy/access", "Access requests require manager approval.", "r1"
        ),
        company_document(
            "policy/onboarding", "Onboarding covers product knowledge.", "r1"
        ),
        company_document(
            "policy/payroll", "Payroll closes on the last business day.", "r1"
        ),
        company_document(
            "policy/refunds",
            "Enterprise refunds are available within thirty days.",
            "r1",
        ),
        company_document(
            "policy/security", "Security incidents page the on-call engineer.", "r1"
        ),
    )


class CompanySource:
    """Mutable provider boundary; it emits canonical pages and owns no state."""

    def __init__(
        self,
        documents: Iterable[KnowledgeDocument] = (),
        *,
        source_id: str = SOURCE_ID,
    ) -> None:
        self.source_id = source_id
        self._documents = {document.external_id: document for document in documents}

    def get(self, external_id: str) -> KnowledgeDocument:
        return self._documents[external_id]

    def put(self, document: KnowledgeDocument) -> None:
        self._documents[document.external_id] = document

    def drop(self, external_id: str) -> None:
        self._documents.pop(external_id, None)

    def live_documents(self) -> tuple[KnowledgeDocument, ...]:
        return tuple(self._documents[key] for key in sorted(self._documents))

    def full_pages(self, page_size: int = 2) -> list[PollPage]:
        """Emit one authoritative full snapshot as ordered, paged PollPages."""

        if page_size < 1:
            raise ValueError("page_size must be positive")
        items = self.live_documents()
        if not items:
            return [PollPage(next_cursor="cursor:full:0", snapshot_complete=True)]
        pages: list[PollPage] = []
        for index, start in enumerate(range(0, len(items), page_size), start=1):
            complete = start + page_size >= len(items)
            pages.append(
                PollPage(
                    upserts=tuple(items[start : start + page_size]),
                    next_cursor=f"cursor:full:{index}" if complete else None,
                    next_checkpoint=None if complete else f"cursor:full:{index}",
                    snapshot_complete=complete,
                )
            )
        return pages

    def incremental_page(
        self,
        *,
        cursor: str,
        upserts: Iterable[KnowledgeDocument] = (),
        tombstones: Iterable[Tombstone] = (),
    ) -> PollPage:
        """Emit one complete incremental page with explicit provider deletions."""

        return PollPage(
            upserts=tuple(upserts),
            tombstones=tuple(tombstones),
            next_cursor=cursor,
            snapshot_complete=True,
        )


class _BrainTransaction:
    """Host-owned staged transaction implementing ``SyncPlanTransaction``.

    Writes are buffered and flushed in ``commit``. Because ``apply_sync_plan``
    verifies the generation before touching the transaction, a stale plan never
    mutates the store or the live projection.
    """

    def __init__(self, brain: CompanyBrain) -> None:
        self._brain = brain
        self.generation = brain.sync_state.generation
        self._upserts: list[KnowledgeDocument] = []
        self._deletes: list[Tombstone] = []
        self.committed_state: SyncState | None = None

    def upsert(self, document: KnowledgeDocument) -> None:
        self._upserts.append(document)

    def delete(self, tombstone: Tombstone) -> None:
        self._deletes.append(tombstone)

    def commit(self, state: SyncState) -> None:
        brain = self._brain
        for document in self._upserts:
            stored = brain.store.get(
                document.source_id, document.external_id, scope=brain.scope
            )
            brain.store.commit(
                document,
                scope=brain.scope,
                expected_revision=stored.revision if stored else None,
            )
            brain.active[document.external_id] = document
        for tombstone in self._deletes:
            brain.active.pop(tombstone.external_id, None)
        brain.sync_state = state
        self.committed_state = state


class CompanyBrain:
    """Host application: revision store, live projection, and sync state."""

    def __init__(self, *, source_id: str = SOURCE_ID, scope: ScopeRef = SCOPE) -> None:
        self.source_id = source_id
        self.scope = scope
        self.store = InMemoryDocumentStore()
        self.active: dict[str, KnowledgeDocument] = {}
        self.sync_state = SyncState()
        self.receipts: list[dict[str, object]] = []

    def transaction(self) -> _BrainTransaction:
        return _BrainTransaction(self)

    def apply(
        self, plan: SyncPlan, *, mode: SyncMode, label: str, page: int = 1
    ) -> dict[str, object]:
        transaction = self.transaction()
        apply_sync_plan(plan, transaction=transaction)
        receipt: dict[str, object] = {
            "label": label,
            "mode": mode.value,
            "page": page,
            "upserts": [document.document_id for document in plan.upserts],
            "deletes": [tombstone.document_id for tombstone in plan.deletes],
            "delete_reasons": [tombstone.reason for tombstone in plan.deletes],
            "unchanged": list(plan.unchanged),
            "snapshot_complete": plan.snapshot_complete,
            "expected_generation": plan.expected_generation,
            "generation": plan.state.generation,
            "cursor": plan.state.cursor,
            "warnings": list(plan.warnings),
        }
        self.receipts.append(receipt)
        return receipt

    def active_external_ids(self) -> list[str]:
        return sorted(document.external_id for document in self.active.values())

    def active_document_ids(self) -> list[str]:
        return sorted(document.document_id for document in self.active.values())


def _ids(receipts: Iterable[dict[str, object]], key: str) -> list[str]:
    collected: list[str] = []
    for receipt in receipts:
        collected.extend(receipt[key])  # type: ignore[arg-type]
    return collected


def run(
    *, page_size: int = 2, source: CompanySource | None = None
) -> dict[str, object]:
    """Run a deterministic continuous-sync session and return its results."""

    source = CompanySource(initial_documents()) if source is None else source
    brain = CompanyBrain()

    # Cycle 1: paginated full snapshot through the lazy planner. Only the
    # terminal page may reconcile absence, so intermediate pages delete nothing.
    snapshot = [
        brain.apply(plan, mode=SyncMode.FULL, label="snapshot", page=index)
        for index, plan in enumerate(
            stream_sync(
                source.full_pages(page_size),
                brain.sync_state,
                source_id=brain.source_id,
                mode=SyncMode.FULL,
            ),
            start=1,
        )
    ]

    # Cycle 2: incremental poll with an edit, an addition, an ACL revision,
    # and an explicit provider tombstone.
    source.put(
        company_document(
            "policy/refunds",
            "Enterprise refunds are available within ninety days.",
            "r2",
        )
    )
    source.put(
        company_document(
            "policy/benefits", "Benefits enrollment opens each November.", "r1"
        )
    )
    source.put(
        company_document(
            "policy/security",
            "Security incidents page the on-call engineer.",
            "r2",
            visibility="restricted",
            principals=(Principal(kind="group", identifier="security"),),
        )
    )
    source.drop("policy/payroll")
    incremental = brain.apply(
        plan_sync(
            brain.sync_state,
            source.incremental_page(
                cursor="cursor:incremental:1",
                upserts=(
                    source.get("policy/benefits"),
                    source.get("policy/refunds"),
                    source.get("policy/security"),
                ),
                tombstones=(
                    Tombstone(source_id=brain.source_id, external_id="policy/payroll"),
                ),
            ),
            source_id=brain.source_id,
            mode=SyncMode.INCREMENTAL,
        ),
        mode=SyncMode.INCREMENTAL,
        label="incremental",
    )
    payroll_id = canonical_document_id(brain.source_id, "policy/payroll")
    payroll_removed = {
        "removed_from_active": "policy/payroll" not in brain.active,
        "removed_from_manifest": payroll_id not in brain.sync_state.manifest,
        "revision_history_length": len(
            brain.store.history(brain.source_id, "policy/payroll", scope=brain.scope)
        ),
    }
    cursor_before_repair = brain.sync_state.cursor

    # Cycle 3: interrupted repair snapshot. The provider dropped access
    # approval, but the snapshot is incomplete, so absence is not deletion.
    source.drop("policy/access")
    live = source.live_documents()
    interrupted = brain.apply(
        plan_sync(
            brain.sync_state,
            PollPage(
                upserts=live[:page_size],
                next_checkpoint="cursor:repair:1",
                snapshot_complete=False,
            ),
            source_id=brain.source_id,
            mode=SyncMode.FULL,
        ),
        mode=SyncMode.FULL,
        label="repair_interrupted",
    )

    # An incomplete full snapshot mode-locks the state until it completes.
    resume_error: str | None = None
    try:
        plan_sync(
            brain.sync_state,
            source.incremental_page(cursor="cursor:incremental:2"),
            source_id=brain.source_id,
            mode=SyncMode.INCREMENTAL,
        )
    except ValueError as error:
        resume_error = str(error)

    # Cycle 4: finish the repair snapshot; the terminal page reconciles absence.
    repair = [
        brain.apply(plan, mode=SyncMode.FULL, label="repair", page=index)
        for index, plan in enumerate(
            stream_sync(
                [
                    PollPage(
                        upserts=live[page_size:],
                        next_cursor="cursor:repair:done",
                        snapshot_complete=True,
                    )
                ],
                brain.sync_state,
                source_id=brain.source_id,
                mode=SyncMode.FULL,
            ),
            start=2,
        )
    ]

    # Cycle 5: two plans from one generation. The first commit advances the
    # generation; the competing plan can no longer be applied.
    base_generation = brain.sync_state.generation
    source.put(
        company_document(
            "policy/refunds",
            "Enterprise refunds are available within ninety days for annual plans.",
            "r3",
        )
    )
    source.put(
        company_document("policy/travel", "Travel requires manager pre-approval.", "r1")
    )
    accepted_plan = plan_sync(
        brain.sync_state,
        source.incremental_page(
            cursor="cursor:incremental:3",
            upserts=(source.get("policy/refunds"),),
        ),
        source_id=brain.source_id,
        mode=SyncMode.INCREMENTAL,
    )
    competing_plan = plan_sync(
        brain.sync_state,
        source.incremental_page(
            cursor="cursor:concurrent:1",
            upserts=(source.get("policy/travel"),),
        ),
        source_id=brain.source_id,
        mode=SyncMode.INCREMENTAL,
    )
    accepted = brain.apply(
        accepted_plan, mode=SyncMode.INCREMENTAL, label="accepted_concurrent"
    )
    conflict: str | None = None
    try:
        apply_sync_plan(competing_plan, transaction=brain.transaction())
    except ValueError as error:
        conflict = str(error)
    travel_pending_before_recovery = "policy/travel" not in brain.active

    # Cycle 6: the next poll repairs the rejected document.
    recovery_page = source.incremental_page(
        cursor="cursor:incremental:4", upserts=source.live_documents()
    )
    recovery = brain.apply(
        plan_sync(
            brain.sync_state,
            recovery_page,
            source_id=brain.source_id,
            mode=SyncMode.INCREMENTAL,
        ),
        mode=SyncMode.INCREMENTAL,
        label="recovery",
    )

    # Cycle 7: replaying the same page is a no-op upsert set.
    replay = brain.apply(
        plan_sync(
            brain.sync_state,
            recovery_page,
            source_id=brain.source_id,
            mode=SyncMode.INCREMENTAL,
        ),
        mode=SyncMode.INCREMENTAL,
        label="replay",
    )

    generations = [receipt["generation"] for receipt in brain.receipts]
    return {
        "source_id": brain.source_id,
        "scope": {"tenant": brain.scope.tenant, "space": brain.scope.space},
        "snapshot_pages": snapshot,
        "snapshot_upserts": _ids(snapshot, "upserts"),
        "snapshot_deletes": _ids(snapshot, "deletes"),
        "snapshot_cursor_held_until_complete": all(
            receipt["cursor"] is None for receipt in snapshot[:-1]
        )
        and snapshot[-1]["cursor"] is not None,
        "incremental": incremental,
        "incremental_upserts": incremental["upserts"],
        "incremental_deletes": incremental["deletes"],
        "incremental_unchanged": incremental["unchanged"],
        "payroll_tombstone": payroll_removed,
        "interrupted": interrupted,
        "interrupted_cursor_held": interrupted["cursor"] == cursor_before_repair,
        "incremental_resume_rejected": resume_error,
        "repair_pages": repair,
        "reconcile_deletes": _ids(repair, "deletes"),
        "reconcile_reasons": _ids(repair, "delete_reasons"),
        "generation_conflict": {
            "base_generation": base_generation,
            "accepted": accepted,
            "competing_expected_generation": competing_plan.expected_generation,
            "competing_error": conflict,
            "competing_document_pending": travel_pending_before_recovery,
        },
        "recovery_upserts": recovery["upserts"],
        "recovery_unchanged": recovery["unchanged"],
        "replay_upserts": replay["upserts"],
        "replay_deletes": replay["deletes"],
        "replay_unchanged": replay["unchanged"],
        "active_external_ids": brain.active_external_ids(),
        "active_document_ids": brain.active_document_ids(),
        "manifest_document_ids": sorted(brain.sync_state.manifest),
        "final_generation": brain.sync_state.generation,
        "final_cursor": brain.sync_state.cursor,
        "generations": generations,
        "generations_strictly_increasing": all(
            later == earlier + 1
            for earlier, later in zip(generations, generations[1:], strict=False)
        ),
        "cycles": len(brain.receipts),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
