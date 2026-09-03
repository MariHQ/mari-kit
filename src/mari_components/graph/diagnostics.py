"""Exact graph diffs and policy-neutral structural observations."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from typing import TypeVar

NodeT = TypeVar("NodeT", bound=Hashable)
EdgeT = TypeVar("EdgeT", bound=Hashable)


@dataclass(frozen=True, slots=True, kw_only=True)
class GraphDiff:
    added_nodes: frozenset[Hashable]
    removed_nodes: frozenset[Hashable]
    added_edges: frozenset[Hashable]
    removed_edges: frozenset[Hashable]
    node_change_rate: float
    edge_change_rate: float


def _change_rate(left: set[EdgeT], right: set[EdgeT]) -> float:
    union = left | right
    return len(left ^ right) / len(union) if union else 0.0


def graph_diff(
    *,
    before_nodes: Iterable[NodeT],
    before_edges: Iterable[EdgeT],
    after_nodes: Iterable[NodeT],
    after_edges: Iterable[EdgeT],
) -> GraphDiff:
    left_nodes, right_nodes = set(before_nodes), set(after_nodes)
    left_edges, right_edges = set(before_edges), set(after_edges)
    return GraphDiff(
        added_nodes=frozenset(right_nodes - left_nodes),
        removed_nodes=frozenset(left_nodes - right_nodes),
        added_edges=frozenset(right_edges - left_edges),
        removed_edges=frozenset(left_edges - right_edges),
        node_change_rate=_change_rate(left_nodes, right_nodes),
        edge_change_rate=_change_rate(left_edges, right_edges),
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class GraphQualityReport:
    node_count: int
    edge_count: int
    density: float
    orphan_nodes: tuple[Hashable, ...]
    dangling_edges: tuple[tuple[Hashable, Hashable], ...]
    self_loops: tuple[tuple[Hashable, Hashable], ...]
    duplicate_groups: tuple[tuple[Hashable, ...], ...]


def inspect_graph_quality(
    *,
    nodes: Iterable[NodeT],
    edges: Iterable[tuple[NodeT, NodeT]],
    fingerprint: Callable[[NodeT], Hashable] | None = None,
    directed: bool = True,
) -> GraphQualityReport:
    node_set = set(nodes)
    edge_values = tuple(edges)
    degree = {node: 0 for node in node_set}
    dangling: list[tuple[NodeT, NodeT]] = []
    loops: list[tuple[NodeT, NodeT]] = []
    for left, right in edge_values:
        if left not in node_set or right not in node_set:
            dangling.append((left, right))
            continue
        degree[left] += 1
        degree[right] += 1
        if left == right:
            loops.append((left, right))
    groups: dict[Hashable, list[NodeT]] = {}
    if fingerprint is not None:
        for node in node_set:
            groups.setdefault(fingerprint(node), []).append(node)
    duplicates = [tuple(sorted(group, key=repr)) for group in groups.values() if len(group) > 1]
    count = len(node_set)
    possible = count * (count - 1) if directed else count * (count - 1) / 2
    valid_non_loop = sum(left in node_set and right in node_set and left != right for left, right in edge_values)
    return GraphQualityReport(
        node_count=count,
        edge_count=len(edge_values),
        density=valid_non_loop / possible if possible else 0.0,
        orphan_nodes=tuple(sorted((node for node, value in degree.items() if value == 0), key=repr)),
        dangling_edges=tuple(sorted(dangling, key=repr)),
        self_loops=tuple(sorted(loops, key=repr)),
        duplicate_groups=tuple(sorted(duplicates, key=repr)),
    )
