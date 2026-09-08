"""Deterministic graph communities and model-injected corpus aggregation."""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class CommunityPartition:
    communities: tuple[tuple[str, ...], ...]
    modularity: float


@dataclass(frozen=True, slots=True, kw_only=True)
class CommunityReport:
    community_id: str
    node_ids: tuple[str, ...]
    text: str


def _normalized_graph(
    graph: Mapping[str, Mapping[str, float]],
    allowed: Collection[str] | None,
) -> dict[str, dict[str, float]]:
    selected = set(graph) if allowed is None else set(graph) & set(allowed)
    output = {node: {} for node in sorted(selected)}
    for left in output:
        for right, raw_weight in graph[left].items():
            if right not in output or left == right:
                continue
            weight = float(raw_weight)
            if not math.isfinite(weight) or weight < 0:
                raise ValueError("graph weights must be finite and non-negative")
            reverse = float(graph.get(right, {}).get(left, weight))
            if not math.isfinite(reverse) or reverse < 0:
                raise ValueError("graph weights must be finite and non-negative")
            combined = (weight + reverse) / 2
            if combined:
                output[left][right] = combined
                output[right][left] = combined
    return output


def _modularity(
    graph: Mapping[str, Mapping[str, float]],
    labels: Mapping[str, int],
    resolution: float,
) -> float:
    degrees = {node: sum(edges.values()) for node, edges in graph.items()}
    twice_weight = sum(degrees.values())
    if twice_weight == 0:
        return 0.0
    score = 0.0
    for left, edges in graph.items():
        for right, weight in edges.items():
            if labels[left] == labels[right]:
                score += (
                    weight - resolution * degrees[left] * degrees[right] / twice_weight
                )
    return score / twice_weight


def _connected_parts(
    graph: Mapping[str, Mapping[str, float]], nodes: Collection[str]
) -> tuple[tuple[str, ...], ...]:
    remaining = set(nodes)
    parts: list[tuple[str, ...]] = []
    while remaining:
        seed = min(remaining)
        queue = deque([seed])
        reached = {seed}
        remaining.remove(seed)
        while queue:
            current = queue.popleft()
            for neighbor in graph[current]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    reached.add(neighbor)
                    queue.append(neighbor)
        parts.append(tuple(sorted(reached)))
    return tuple(parts)


def leiden_communities(
    graph: Mapping[str, Mapping[str, float]],
    *,
    resolution: float = 1.0,
    allowed_node_ids: Collection[str] | None = None,
    max_passes: int = 20,
) -> CommunityPartition:
    """Optimize modularity, then refine every community to connected parts.

    Historical compatibility name: this is a local-modularity heuristic with
    connected-component splitting, not the full Leiden algorithm (it has no
    aggregation phase). For native hierarchical Leiden use
    algorithms.graphs.hierarchical_leiden_partition.
    """

    if not math.isfinite(resolution) or resolution <= 0 or max_passes < 1:
        raise ValueError("resolution and max_passes must be positive")
    values = _normalized_graph(graph, allowed_node_ids)
    if not values:
        return CommunityPartition(communities=(), modularity=0.0)
    labels = {node: index for index, node in enumerate(values)}
    score = _modularity(values, labels, resolution)
    for _ in range(max_passes):
        changed = False
        for node in sorted(values):
            current = labels[node]
            candidates = sorted(
                {labels[neighbor] for neighbor in values[node]} | {current}
            )
            best = (score, -current, current)
            for candidate in candidates:
                trial = dict(labels)
                trial[node] = candidate
                candidate_score = _modularity(values, trial, resolution)
                choice = (candidate_score, -candidate, candidate)
                if choice > best:
                    best = choice
            if best[2] != current and best[0] > score + 1e-12:
                labels[node] = best[2]
                score = best[0]
                changed = True
        if not changed:
            break
    grouped: dict[int, set[str]] = {}
    for node, label in labels.items():
        grouped.setdefault(label, set()).add(node)
    communities = tuple(
        sorted(
            (
                part
                for nodes in grouped.values()
                for part in _connected_parts(values, nodes)
            ),
            key=lambda part: (part[0], len(part), part),
        )
    )
    refined = {
        node: index for index, community in enumerate(communities) for node in community
    }
    return CommunityPartition(
        communities=communities,
        modularity=_modularity(values, refined, resolution),
    )


def build_community_reports(
    partition: CommunityPartition,
    *,
    summarize: Callable[[tuple[str, ...]], str],
) -> tuple[CommunityReport, ...]:
    """Build one externally summarized report per deterministic community."""

    reports = []
    for index, nodes in enumerate(partition.communities):
        text = summarize(nodes).strip()
        if not text:
            raise ValueError("community summaries must not be empty")
        reports.append(
            CommunityReport(
                community_id=f"community:{index}", node_ids=nodes, text=text
            )
        )
    return tuple(reports)


def map_reduce_reports(
    reports: Sequence[CommunityReport],
    *,
    map_report: Callable[[CommunityReport], str | None],
    reduce_answers: Callable[[tuple[str, ...]], str],
    limit: int = 24,
) -> str:
    """Map bounded community reports and reduce non-empty partial answers."""

    if limit < 1:
        raise ValueError("limit must be positive")
    partials = tuple(
        answer.strip()
        for report in reports[:limit]
        if (answer := map_report(report)) is not None and answer.strip()
    )
    return reduce_answers(partials)
