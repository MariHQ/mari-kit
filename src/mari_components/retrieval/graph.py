"""Deterministic graph propagation and passage projection for retrieval."""

from __future__ import annotations

import math
from collections.abc import Collection, Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class GraphHit:
    node_id: str
    score: float


@dataclass(frozen=True, slots=True, kw_only=True)
class PageRankResult:
    hits: tuple[GraphHit, ...]
    iterations: int
    converged: bool


def personalized_pagerank(
    graph: Mapping[str, Mapping[str, float]],
    seeds: Mapping[str, float],
    *,
    damping: float = 0.85,
    tolerance: float = 1e-9,
    max_iterations: int = 200,
    allowed_node_ids: Collection[str] | None = None,
) -> PageRankResult:
    """Propagate a seed distribution across a weighted directed graph.

    The induced allowed-node graph is built before normalization and iteration.
    Dangling mass returns to the personalized seed distribution. Convergence uses
    L1 distance and the result reports whether the iteration budget was enough.
    """
    if not math.isfinite(damping) or not 0 <= damping < 1:
        raise ValueError("damping must be a finite value in [0, 1)")
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("tolerance must be a positive finite number")
    if max_iterations < 1:
        raise ValueError("max_iterations must be positive")

    nodes = {str(node) for node in graph} | {str(node) for node in seeds}
    for edges in graph.values():
        nodes.update(str(node) for node in edges)
    if allowed_node_ids is not None:
        nodes &= {str(node) for node in allowed_node_ids}
    if not nodes:
        return PageRankResult(hits=(), iterations=0, converged=True)

    seed_values: dict[str, float] = {}
    for node in nodes:
        value = float(seeds.get(node, 0.0))
        if not math.isfinite(value) or value < 0:
            raise ValueError("seed weights must be non-negative finite numbers")
        seed_values[node] = value
    seed_total = sum(seed_values.values())
    if seed_total <= 0:
        raise ValueError("at least one allowed seed must have positive weight")
    personalization = {node: value / seed_total for node, value in seed_values.items()}

    transitions: dict[str, dict[str, float]] = {}
    for node in nodes:
        raw_edges = graph.get(node, {})
        clean: dict[str, float] = {}
        for target, raw_weight in raw_edges.items():
            target_id = str(target)
            weight = float(raw_weight)
            if not math.isfinite(weight) or weight < 0:
                raise ValueError("edge weights must be non-negative finite numbers")
            if target_id in nodes and weight > 0:
                clean[target_id] = clean.get(target_id, 0.0) + weight
        total = sum(clean.values())
        transitions[node] = (
            {target: weight / total for target, weight in clean.items()}
            if total
            else {}
        )

    rank = dict(personalization)
    converged = False
    iterations = 0
    for iteration in range(1, max_iterations + 1):
        iterations = iteration
        next_rank = {node: (1 - damping) * personalization[node] for node in nodes}
        dangling = sum(rank[node] for node in nodes if not transitions[node])
        for node in nodes:
            next_rank[node] += damping * dangling * personalization[node]
        for source, edges in transitions.items():
            for target, probability in edges.items():
                next_rank[target] += damping * rank[source] * probability
        distance = sum(abs(next_rank[node] - rank[node]) for node in nodes)
        rank = next_rank
        if distance <= tolerance:
            converged = True
            break

    hits = tuple(
        GraphHit(node_id=node, score=rank[node])
        for node in sorted(nodes, key=lambda node: (-rank[node], node))
    )
    return PageRankResult(hits=hits, iterations=iterations, converged=converged)


def project_graph_scores(
    node_scores: Mapping[str, float] | tuple[GraphHit, ...],
    node_passages: Mapping[str, Mapping[str, float]],
    *,
    limit: int | None = None,
) -> tuple[GraphHit, ...]:
    """Project propagated node scores onto passages through weighted incidence."""
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")
    scores = (
        {hit.node_id: hit.score for hit in node_scores}
        if isinstance(node_scores, tuple)
        else dict(node_scores)
    )
    passages: dict[str, float] = {}
    for node, score in scores.items():
        value = float(score)
        if not math.isfinite(value):
            raise ValueError("node scores must be finite")
        for passage, raw_weight in node_passages.get(node, {}).items():
            weight = float(raw_weight)
            if not math.isfinite(weight) or weight < 0:
                raise ValueError(
                    "incidence weights must be non-negative finite numbers"
                )
            passages[str(passage)] = passages.get(str(passage), 0.0) + value * weight
    ordered = sorted(passages, key=lambda passage: (-passages[passage], passage))
    if limit is not None:
        ordered = ordered[:limit]
    return tuple(
        GraphHit(node_id=passage, score=passages[passage]) for passage in ordered
    )
