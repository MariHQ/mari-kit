"""Bounded lineage and taint traversal over arbitrary artifact IDs."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
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


@dataclass(frozen=True, slots=True, kw_only=True)
class LineageEdge:
    child_id: Hashable
    parent_id: Hashable
    role: str = "input"
    operation: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.role.strip():
            raise ValueError("lineage edge role is required")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True, kw_only=True)
class LineageEdgeTrace:
    artifact_ids: tuple[Hashable, ...]
    edges: tuple[LineageEdge, ...]
    cycle_edges: tuple[LineageEdge, ...]
    truncated: bool


def trace_lineage_edges(
    artifact_id: IdT,
    *,
    parents: Callable[[IdT], Iterable[LineageEdge]],
    max_depth: int = 20,
    max_artifacts: int = 10_000,
) -> LineageEdgeTrace:
    """Trace bounded lineage while preserving caller-defined edge metadata."""

    if max_depth < 0 or max_artifacts < 1:
        raise ValueError("lineage bounds are invalid")
    queue: deque[tuple[IdT, int, frozenset[IdT]]] = deque(
        [(artifact_id, 0, frozenset({artifact_id}))]
    )
    visited: set[IdT] = set()
    traversed: list[LineageEdge] = []
    cycles: list[LineageEdge] = []
    truncated = False
    while queue:
        item, depth, branch = queue.popleft()
        if item in visited:
            continue
        if len(visited) >= max_artifacts:
            truncated = True
            break
        visited.add(item)
        parent_edges = tuple(parents(item))
        if depth >= max_depth:
            truncated = truncated or bool(parent_edges)
            continue
        for edge in sorted(parent_edges, key=lambda value: repr(value.parent_id)):
            if edge.child_id != item:
                raise ValueError("lineage edge child must match the expanded artifact")
            parent = cast(IdT, edge.parent_id)
            if parent in branch:
                cycles.append(edge)
            else:
                traversed.append(edge)
                if parent not in visited:
                    queue.append((parent, depth + 1, branch | {parent}))
    return LineageEdgeTrace(
        artifact_ids=tuple(sorted(visited, key=repr)),
        edges=tuple(traversed),
        cycle_edges=tuple(cycles),
        truncated=truncated,
    )


def trace_lineage(
    artifact_id: IdT,
    *,
    parents: Callable[[IdT], Iterable[IdT]],
    max_depth: int = 20,
    max_artifacts: int = 10_000,
) -> LineageTrace:
    if max_depth < 0 or max_artifacts < 1:
        raise ValueError("lineage bounds are invalid")
    queue: deque[tuple[IdT, int, IdT | None, frozenset[IdT]]] = deque(
        [(artifact_id, 0, None, frozenset({artifact_id}))]
    )
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
    return LineageTrace(
        visits=tuple(visits),
        cycle_edges=tuple(sorted(cycles, key=repr)),
        truncated=truncated,
    )


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
