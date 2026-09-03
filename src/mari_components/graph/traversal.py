"""Graph traversal over caller-owned node IDs and neighbor callbacks."""

from __future__ import annotations

import heapq
import math
from collections import deque
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from typing import TypeVar, cast

NodeT = TypeVar("NodeT", bound=Hashable)


def _stable(value: Hashable) -> tuple[str, str]:
    return type(value).__qualname__, repr(value)


@dataclass(frozen=True, slots=True, kw_only=True)
class TraversalVisit:
    node: Hashable
    depth: int
    parent: Hashable | None


@dataclass(frozen=True, slots=True, kw_only=True)
class TraversalResult:
    visits: tuple[TraversalVisit, ...]
    truncated: bool

    @property
    def nodes(self) -> tuple[Hashable, ...]:
        return tuple(visit.node for visit in self.visits)


@dataclass(frozen=True, slots=True, kw_only=True)
class PathResult:
    nodes: tuple[Hashable, ...]
    cost: float
    visited_count: int
    truncated: bool = False

    @property
    def found(self) -> bool:
        return bool(self.nodes)


@dataclass(frozen=True, slots=True, kw_only=True)
class CycleResult:
    cycles: tuple[tuple[Hashable, ...], ...]
    truncated: bool


def breadth_first(
    starts: Iterable[NodeT],
    *,
    neighbors: Callable[[NodeT], Iterable[NodeT]],
    allowed: Callable[[NodeT], bool] = lambda _node: True,
    max_depth: int | None = None,
    max_nodes: int | None = None,
) -> TraversalResult:
    if max_depth is not None and max_depth < 0:
        raise ValueError("max_depth must not be negative")
    if max_nodes is not None and max_nodes < 1:
        raise ValueError("max_nodes must be positive")
    queue: deque[tuple[NodeT, int, NodeT | None]] = deque(
        (node, 0, None) for node in sorted(set(starts), key=_stable) if allowed(node)
    )
    seen: set[NodeT] = set()
    visits: list[TraversalVisit] = []
    truncated = False
    while queue:
        node, depth, parent = queue.popleft()
        if node in seen:
            continue
        if max_nodes is not None and len(visits) >= max_nodes:
            truncated = True
            break
        seen.add(node)
        visits.append(TraversalVisit(node=node, depth=depth, parent=parent))
        if max_depth is not None and depth >= max_depth:
            continue
        for adjacent in sorted(set(neighbors(node)), key=_stable):
            if adjacent not in seen and allowed(adjacent):
                queue.append((adjacent, depth + 1, node))
    return TraversalResult(visits=tuple(visits), truncated=truncated)


def k_hop_nodes(
    starts: Iterable[NodeT],
    *,
    neighbors: Callable[[NodeT], Iterable[NodeT]],
    hops: int,
    allowed: Callable[[NodeT], bool] = lambda _node: True,
    max_nodes: int | None = None,
) -> TraversalResult:
    return breadth_first(
        starts,
        neighbors=neighbors,
        allowed=allowed,
        max_depth=hops,
        max_nodes=max_nodes,
    )


def shortest_path(
    start: NodeT,
    target: NodeT,
    *,
    neighbors: Callable[[NodeT], Iterable[NodeT]],
    edge_cost: Callable[[NodeT, NodeT], float] = lambda _left, _right: 1.0,
    allowed: Callable[[NodeT], bool] = lambda _node: True,
    max_depth: int | None = None,
    max_visited: int | None = None,
) -> PathResult:
    if max_depth is not None and max_depth < 0:
        raise ValueError("max_depth must not be negative")
    if max_visited is not None and max_visited < 1:
        raise ValueError("max_visited must be positive")
    if not allowed(start) or not allowed(target):
        return PathResult(nodes=(), cost=math.inf, visited_count=0)
    counter = 0
    heap: list[tuple[float, int, int, NodeT, tuple[NodeT, ...]]] = [(0.0, 0, counter, start, (start,))]
    best: dict[NodeT, float] = {start: 0.0}
    visited = 0
    while heap:
        cost, depth, _, node, path = heapq.heappop(heap)
        if cost != best.get(node):
            continue
        if max_visited is not None and visited >= max_visited:
            return PathResult(nodes=(), cost=math.inf, visited_count=visited, truncated=True)
        visited += 1
        if node == target:
            return PathResult(nodes=path, cost=cost, visited_count=visited)
        if max_depth is not None and depth >= max_depth:
            continue
        for adjacent in sorted(set(neighbors(node)), key=_stable):
            if not allowed(adjacent):
                continue
            step = float(edge_cost(node, adjacent))
            if not math.isfinite(step) or step < 0:
                raise ValueError("edge costs must be finite and non-negative")
            candidate = cost + step
            if candidate < best.get(adjacent, math.inf):
                best[adjacent] = candidate
                counter += 1
                heapq.heappush(heap, (candidate, depth + 1, counter, adjacent, (*path, adjacent)))
    return PathResult(nodes=(), cost=math.inf, visited_count=visited)


def connected_components(
    nodes: Iterable[NodeT], *, neighbors: Callable[[NodeT], Iterable[NodeT]]
) -> tuple[tuple[NodeT, ...], ...]:
    remaining = set(nodes)
    components: list[tuple[NodeT, ...]] = []
    while remaining:
        start = min(remaining, key=_stable)
        result = breadth_first((start,), neighbors=lambda node: (item for item in neighbors(node) if item in remaining))
        component = cast(tuple[NodeT, ...], tuple(result.nodes))
        remaining.difference_update(component)
        components.append(component)
    return tuple(sorted(components, key=lambda part: (-len(part), tuple(_stable(item) for item in part))))


def directed_cycles(
    nodes: Iterable[NodeT],
    *,
    neighbors: Callable[[NodeT], Iterable[NodeT]],
    max_cycles: int = 100,
    max_depth: int = 20,
) -> CycleResult:
    """Enumerate bounded simple directed cycles with canonical rotations."""

    if max_cycles < 1 or max_depth < 1:
        raise ValueError("cycle limits must be positive")
    known = set(nodes)
    cycles: set[tuple[NodeT, ...]] = set()

    def canonical(cycle: tuple[NodeT, ...]) -> tuple[NodeT, ...]:
        rotations = [cycle[index:] + cycle[:index] for index in range(len(cycle))]
        return min(rotations, key=lambda row: tuple(_stable(item) for item in row))

    truncated = False
    for start in sorted(known, key=_stable):
        stack: list[tuple[NodeT, tuple[NodeT, ...]]] = [(start, (start,))]
        while stack:
            node, path = stack.pop()
            if len(path) > max_depth:
                truncated = True
                continue
            for adjacent in sorted((item for item in set(neighbors(node)) if item in known), key=_stable, reverse=True):
                if adjacent == start:
                    cycles.add(canonical(path))
                    if len(cycles) >= max_cycles:
                        return CycleResult(cycles=tuple(sorted(cycles, key=repr)), truncated=True)
                elif adjacent not in path:
                    stack.append((adjacent, (*path, adjacent)))
    return CycleResult(cycles=tuple(sorted(cycles, key=repr)), truncated=truncated)
