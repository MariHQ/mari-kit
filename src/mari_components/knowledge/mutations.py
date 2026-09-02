"""Validated, storage-neutral memory mutation plans."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar

ValueT = TypeVar("ValueT")


class MemoryOperation(StrEnum):
    ADD = "add"
    UPDATE = "update"
    DELETE = "delete"
    NOOP = "noop"


@dataclass(frozen=True, slots=True, kw_only=True)
class MemoryDecision:
    """An externally produced operation classification for one candidate."""

    operation: MemoryOperation
    target_id: str = ""
    reason: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class MemoryMutation(Generic[ValueT]):
    operation: MemoryOperation
    candidate_id: str
    target_id: str
    value: ValueT | None = None
    reason: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class MemoryMutationPlan(Generic[ValueT]):
    mutations: tuple[MemoryMutation[ValueT], ...]

    @property
    def writes(self) -> tuple[MemoryMutation[ValueT], ...]:
        return tuple(
            row
            for row in self.mutations
            if row.operation in {MemoryOperation.ADD, MemoryOperation.UPDATE}
        )

    @property
    def deletes(self) -> tuple[MemoryMutation[ValueT], ...]:
        return tuple(
            row for row in self.mutations if row.operation is MemoryOperation.DELETE
        )

    @property
    def noops(self) -> tuple[MemoryMutation[ValueT], ...]:
        return tuple(
            row for row in self.mutations if row.operation is MemoryOperation.NOOP
        )


def plan_memory_mutations(
    existing: Mapping[str, ValueT],
    candidates: Mapping[str, ValueT],
    decisions: Mapping[str, MemoryDecision],
) -> MemoryMutationPlan[ValueT]:
    """Validate ADD/UPDATE/DELETE/NOOP decisions without writing storage.

    Candidate IDs make classifier output joinable and auditable. ADD uses the
    candidate ID unless a target is supplied. UPDATE and DELETE require an
    existing target. Conflicting operations against one target are rejected.
    """
    missing = set(candidates) - set(decisions)
    extra = set(decisions) - set(candidates)
    if missing or extra:
        raise ValueError(
            f"decisions must match candidates; missing={sorted(missing)!r}, extra={sorted(extra)!r}"
        )

    mutations: list[MemoryMutation[ValueT]] = []
    claimed_targets: set[str] = set()
    for candidate_id in sorted(candidates):
        if not candidate_id:
            raise ValueError("candidate IDs must not be empty")
        decision = decisions[candidate_id]
        operation = MemoryOperation(decision.operation)
        target_id = decision.target_id.strip()
        value: ValueT | None = None

        if operation is MemoryOperation.ADD:
            target_id = target_id or candidate_id
            if target_id in existing:
                raise ValueError(f"ADD target already exists: {target_id!r}")
            value = candidates[candidate_id]
        elif operation is MemoryOperation.UPDATE:
            if not target_id or target_id not in existing:
                raise ValueError("UPDATE requires an existing target_id")
            value = candidates[candidate_id]
        elif operation is MemoryOperation.DELETE:
            if not target_id or target_id not in existing:
                raise ValueError("DELETE requires an existing target_id")
        elif target_id:
            raise ValueError("NOOP must not specify a target_id")

        if operation is not MemoryOperation.NOOP:
            if target_id in claimed_targets:
                raise ValueError(f"multiple mutations target {target_id!r}")
            claimed_targets.add(target_id)
        mutations.append(
            MemoryMutation(
                operation=operation,
                candidate_id=candidate_id,
                target_id=target_id,
                value=value,
                reason=decision.reason,
            )
        )
    return MemoryMutationPlan(mutations=tuple(mutations))


def apply_memory_mutations(
    existing: Mapping[str, ValueT], plan: MemoryMutationPlan[ValueT]
) -> dict[str, ValueT]:
    """Return the projected store after applying a validated mutation plan."""
    output = dict(existing)
    for mutation in plan.mutations:
        if mutation.operation in {MemoryOperation.ADD, MemoryOperation.UPDATE}:
            if mutation.value is None:
                raise ValueError("write mutations require a value")
            output[mutation.target_id] = mutation.value
        elif mutation.operation is MemoryOperation.DELETE:
            if mutation.target_id not in output:
                raise ValueError(
                    f"DELETE target does not exist: {mutation.target_id!r}"
                )
            del output[mutation.target_id]
    return output
