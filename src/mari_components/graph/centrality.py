"""Reference centrality algorithms over neighbor callbacks."""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Callable, Hashable, Iterable
from typing import TypeVar

NodeT = TypeVar("NodeT", bound=Hashable)


def degree_centrality(
    nodes: Iterable[NodeT], *, neighbors: Callable[[NodeT], Iterable[NodeT]]
) -> tuple[tuple[NodeT, float], ...]:
    values = tuple(set(nodes))
    scale = max(1, len(values) - 1)
    return tuple(
        sorted(
            ((node, len(set(neighbors(node))) / scale) for node in values),
            key=lambda item: (-item[1], repr(item[0])),
        )
    )


def closeness_centrality(
    nodes: Iterable[NodeT], *, neighbors: Callable[[NodeT], Iterable[NodeT]]
) -> tuple[tuple[NodeT, float], ...]:
    values = tuple(set(nodes))
    scores: list[tuple[NodeT, float]] = []
    for source in values:
        distances = {source: 0}
        queue = deque([source])
        while queue:
            node = queue.popleft()
            for adjacent in set(neighbors(node)):
                if adjacent not in distances:
                    distances[adjacent] = distances[node] + 1
                    queue.append(adjacent)
        reachable = len(distances) - 1
        distance_sum = sum(distances.values())
        score = (
            (reachable / distance_sum) * (reachable / max(1, len(values) - 1))
            if distance_sum
            else 0.0
        )
        scores.append((source, score))
    return tuple(sorted(scores, key=lambda item: (-item[1], repr(item[0]))))


def betweenness_centrality(
    nodes: Iterable[NodeT],
    *,
    neighbors: Callable[[NodeT], Iterable[NodeT]],
    normalized: bool = True,
) -> tuple[tuple[NodeT, float], ...]:
    """Unweighted directed Brandes betweenness centrality."""

    values = tuple(sorted(set(nodes), key=repr))
    centrality = dict.fromkeys(values, 0.0)
    for source in values:
        stack: list[NodeT] = []
        predecessors: dict[NodeT, list[NodeT]] = {node: [] for node in values}
        paths = dict.fromkeys(values, 0.0)
        paths[source] = 1.0
        distance = dict.fromkeys(values, -1)
        distance[source] = 0
        queue = deque([source])
        while queue:
            node = queue.popleft()
            stack.append(node)
            for adjacent in set(neighbors(node)):
                if adjacent not in distance:
                    continue
                if distance[adjacent] < 0:
                    queue.append(adjacent)
                    distance[adjacent] = distance[node] + 1
                if distance[adjacent] == distance[node] + 1:
                    paths[adjacent] += paths[node]
                    predecessors[adjacent].append(node)
        dependency = dict.fromkeys(values, 0.0)
        while stack:
            node = stack.pop()
            if paths[node]:
                for parent in predecessors[node]:
                    dependency[parent] += (paths[parent] / paths[node]) * (
                        1.0 + dependency[node]
                    )
            if node != source:
                centrality[node] += dependency[node]
    if normalized and len(values) > 2:
        scale = 1.0 / ((len(values) - 1) * (len(values) - 2))
        centrality = {node: value * scale for node, value in centrality.items()}
    return tuple(sorted(centrality.items(), key=lambda item: (-item[1], repr(item[0]))))


def hits(
    nodes: Iterable[NodeT],
    *,
    successors: Callable[[NodeT], Iterable[NodeT]],
    iterations: int = 100,
    tolerance: float = 1e-8,
) -> tuple[tuple[NodeT, float, float], ...]:
    """Return node, hub score, authority score using power iteration."""

    values = tuple(sorted(set(nodes), key=repr))
    if iterations < 1 or tolerance < 0:
        raise ValueError("iterations must be positive and tolerance non-negative")
    if not values:
        return ()
    known = set(values)
    outgoing = {
        node: tuple(item for item in set(successors(node)) if item in known)
        for node in values
    }
    incoming = {node: [] for node in values}
    for left, targets in outgoing.items():
        for right in targets:
            incoming[right].append(left)
    hubs = dict.fromkeys(values, 1.0 / len(values))
    authorities = dict(hubs)
    for _ in range(iterations):
        new_authorities = {
            node: sum(hubs[parent] for parent in incoming[node]) for node in values
        }
        norm = (
            math.sqrt(sum(value * value for value in new_authorities.values())) or 1.0
        )
        new_authorities = {
            node: value / norm for node, value in new_authorities.items()
        }
        new_hubs = {
            node: sum(new_authorities[target] for target in outgoing[node])
            for node in values
        }
        norm = math.sqrt(sum(value * value for value in new_hubs.values())) or 1.0
        new_hubs = {node: value / norm for node, value in new_hubs.items()}
        delta = sum(
            abs(new_hubs[node] - hubs[node])
            + abs(new_authorities[node] - authorities[node])
            for node in values
        )
        hubs, authorities = new_hubs, new_authorities
        if delta <= tolerance:
            break
    return tuple((node, hubs[node], authorities[node]) for node in values)
