"""Bounded lineage and taint traversal over arbitrary artifact IDs."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from typing import TypeVar, cast

IdT = TypeVar("IdT", bound=Hashable)


@dataclass(frozen=True, slots=True, kw_only=True)
class LineageVisit:
    artifact_id: Hashable
    depth: int
    child_id: Hashable | None


@dataclass(frozen=True, slots=True, kw_only=True)
class LineageTrace:
    visits: tuple[LineageVisit, ...]
    cycle_edges: tuple[tuple[Hashable, Hashable], ...]
    truncated: bool


def trace_lineage(
    artifact_id: IdT,
    *,
    parents: Callable[[IdT], Iterable[IdT]],
    max_depth: int = 20,
    max_artifacts: int = 10_000,
) -> LineageTrace:
    if max_depth < 0 or max_artifacts < 1:
        raise ValueError("lineage bounds are invalid")
    queue: deque[tuple[IdT, int, IdT | None, frozenset[IdT]]] = deque([(artifact_id, 0, None, frozenset({artifact_id}))])
    visited: set[IdT] = set()
    visits: list[LineageVisit] = []
    cycles: set[tuple[IdT, IdT]] = set()
    truncated = False
    while queue:
        item, depth, child, branch = queue.popleft()
        if item in visited:
            continue
        if len(visits) >= max_artifacts:
            truncated = True
            break
        visited.add(item)
        visits.append(LineageVisit(artifact_id=item, depth=depth, child_id=child))
        if depth >= max_depth:
            if tuple(parents(item)):
                truncated = True
            continue
        for parent in sorted(set(parents(item)), key=repr):
            if parent in branch:
                cycles.add((item, parent))
            elif parent not in visited:
                queue.append((parent, depth + 1, item, branch | {parent}))
    return LineageTrace(visits=tuple(visits), cycle_edges=tuple(sorted(cycles, key=repr)), truncated=truncated)


def propagated_taints(
    artifact_id: IdT,
    *,
    parents: Callable[[IdT], Iterable[IdT]],
    taints: Callable[[IdT], Iterable[str]],
    max_depth: int = 20,
) -> tuple[str, ...]:
    trace = trace_lineage(artifact_id, parents=parents, max_depth=max_depth)
    return tuple(
        sorted(
            {
                taint
                for visit in trace.visits
                for taint in taints(cast(IdT, visit.artifact_id))
            }
        )
    )
