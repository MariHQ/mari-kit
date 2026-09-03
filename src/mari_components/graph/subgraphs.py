"""Budgeted selection over caller-owned graph topology."""

from __future__ import annotations

import math
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from typing import TypeVar

from .traversal import _stable

NodeT = TypeVar("NodeT", bound=Hashable)


@dataclass(frozen=True, slots=True, kw_only=True)
class SubgraphSelection:
    nodes: tuple[Hashable, ...]
    edges: tuple[tuple[Hashable, Hashable], ...]
    total_prize: float
    total_cost: float
    rejected: tuple[Hashable, ...]
    truncated: bool


def bounded_seed_expansion(
    *,
    seeds: Iterable[NodeT],
    neighbors: Callable[[NodeT], Iterable[NodeT]],
    score: Callable[[NodeT], float],
    max_nodes: int,
    max_depth: int,
    allowed: Callable[[NodeT], bool] = lambda _node: True,
) -> SubgraphSelection:
    if max_nodes < 1 or max_depth < 0:
        raise ValueError("max_nodes must be positive and max_depth non-negative")
    selected = {node for node in seeds if allowed(node)}
    selected = set(sorted(selected, key=_stable)[:max_nodes])
    edges: set[tuple[NodeT, NodeT]] = set()
    frontier = [(node, 0) for node in selected]
    rejected: set[NodeT] = set()
    while frontier and len(selected) < max_nodes:
        candidates: list[tuple[float, tuple[str, str], NodeT, NodeT, int]] = []
        for parent, depth in frontier:
            if depth >= max_depth:
                continue
            for node in set(neighbors(parent)):
                if node not in selected and allowed(node):
                    value = float(score(node))
                    if not math.isfinite(value):
                        raise ValueError("node scores must be finite")
                    candidates.append((-value, _stable(node), node, parent, depth + 1))
        if not candidates:
            break
        candidates.sort(key=lambda item: (item[0], item[1], _stable(item[3])))
        next_frontier: list[tuple[NodeT, int]] = []
        for _, _, node, parent, depth in candidates:
            if node in selected:
                continue
            if len(selected) >= max_nodes:
                rejected.add(node)
                continue
            selected.add(node)
            edges.add((parent, node))
            next_frontier.append((node, depth))
        frontier = next_frontier
    return SubgraphSelection(
        nodes=tuple(sorted(selected, key=_stable)),
        edges=tuple(sorted(edges, key=lambda edge: (_stable(edge[0]), _stable(edge[1])))),
        total_prize=sum(float(score(node)) for node in selected),
        total_cost=float(len(edges)),
        rejected=tuple(sorted(rejected, key=_stable)),
        truncated=bool(rejected),
    )


def prize_guided_subgraph(
    *,
    seeds: Iterable[NodeT],
    neighbors: Callable[[NodeT], Iterable[NodeT]],
    prize: Callable[[NodeT], float],
    edge_cost: Callable[[NodeT, NodeT], float],
    max_nodes: int,
    allowed: Callable[[NodeT], bool] = lambda _node: True,
) -> SubgraphSelection:
    """Greedily add positive net-value adjacent nodes while preserving connectivity."""

    if max_nodes < 1:
        raise ValueError("max_nodes must be positive")
    selected = {node for node in seeds if allowed(node)}
    if not selected:
        return SubgraphSelection(nodes=(), edges=(), total_prize=0.0, total_cost=0.0, rejected=(), truncated=False)
    selected = set(sorted(selected, key=_stable)[:max_nodes])
    edges: set[tuple[NodeT, NodeT]] = set()
    total_cost = 0.0
    rejected: set[NodeT] = set()
    while len(selected) < max_nodes:
        frontier: list[tuple[float, tuple[str, str], NodeT, NodeT, float]] = []
        for parent in sorted(selected, key=_stable):
            for node in set(neighbors(parent)):
                if node in selected or not allowed(node):
                    continue
                node_prize = float(prize(node))
                cost = float(edge_cost(parent, node))
                if not math.isfinite(node_prize) or not math.isfinite(cost) or cost < 0:
                    raise ValueError("prizes and non-negative edge costs must be finite")
                frontier.append((-(node_prize - cost), _stable(node), parent, node, cost))
        if not frontier:
            break
        frontier.sort(key=lambda item: (item[0], item[1], _stable(item[2])))
        negative_net, _, parent, node, cost = frontier[0]
        if negative_net >= 0:
            rejected.update(item[3] for item in frontier)
            break
        selected.add(node)
        edges.add((parent, node))
        total_cost += cost
    return SubgraphSelection(
        nodes=tuple(sorted(selected, key=_stable)),
        edges=tuple(sorted(edges, key=lambda edge: (_stable(edge[0]), _stable(edge[1])))),
        total_prize=sum(float(prize(node)) for node in selected),
        total_cost=total_cost,
        rejected=tuple(sorted(rejected, key=_stable)),
        truncated=len(selected) >= max_nodes,
    )
