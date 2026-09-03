"""Transaction protocol and conformance helper for applying synchronization plans."""

from __future__ import annotations

from typing import Protocol

from mari_components.types import KnowledgeDocument, Tombstone

from .planning import SyncPlan, SyncState


class SyncPlanTransaction(Protocol):
    """Caller-owned atomic transaction; Mari does not supply persistence."""

    @property
    def generation(self) -> int: ...

    def upsert(self, document: KnowledgeDocument) -> None: ...

    def delete(self, tombstone: Tombstone) -> None: ...

    def commit(self, state: SyncState) -> None: ...


def apply_sync_plan(plan: SyncPlan, *, transaction: SyncPlanTransaction) -> None:
    """Apply a plan after an optimistic generation check and commit its state."""

    if transaction.generation != plan.expected_generation:
        raise ValueError(
            f"sync generation mismatch: expected {plan.expected_generation}, "
            f"found {transaction.generation}"
        )
    for document in plan.upserts:
        transaction.upsert(document)
    for tombstone in plan.deletes:
        transaction.delete(tombstone)
    transaction.commit(plan.state)
