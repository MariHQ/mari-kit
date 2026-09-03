"""Component metrics for graph construction and selection."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass

from .metrics import SetMetrics, set_metrics


@dataclass(frozen=True, slots=True, kw_only=True)
class LinkPredictionMetrics:
    hits_at_k: float
    mean_reciprocal_rank: float
    evaluated_sources: int


@dataclass(frozen=True, slots=True, kw_only=True)
class PathMetrics:
    exact_match: bool
    node_precision: float
    node_recall: float
    edge_precision: float
    edge_recall: float


def evaluate_path(
    predicted: Sequence[Hashable], expected: Sequence[Hashable]
) -> PathMetrics:
    """Compare paths without imposing graph or storage semantics."""
    predicted_edges = set(zip(predicted, predicted[1:], strict=False))
    expected_edges = set(zip(expected, expected[1:], strict=False))
    node_scores = set_metrics(set(expected), set(predicted))
    edge_scores = set_metrics(expected_edges, predicted_edges)
    return PathMetrics(
        exact_match=tuple(predicted) == tuple(expected),
        node_precision=node_scores.precision,
        node_recall=node_scores.recall,
        edge_precision=edge_scores.precision,
        edge_recall=edge_scores.recall,
    )


def evaluate_link_prediction(
    rankings: Mapping[Hashable, Sequence[Hashable]],
    expected: Mapping[Hashable, Iterable[Hashable]],
    *,
    k: int = 10,
) -> LinkPredictionMetrics:
    if k < 1:
        raise ValueError("k must be positive")
    reciprocal: list[float] = []
    hits = 0
    for source in sorted(expected, key=repr):
        relevant = set(expected[source])
        ranking = rankings.get(source, ())[:k]
        rank = next(
            (index for index, value in enumerate(ranking, 1) if value in relevant), None
        )
        hits += rank is not None
        reciprocal.append(1.0 / rank if rank is not None else 0.0)
    count = len(reciprocal)
    return LinkPredictionMetrics(
        hits_at_k=hits / count if count else 0.0,
        mean_reciprocal_rank=sum(reciprocal) / count if count else 0.0,
        evaluated_sources=count,
    )


def evaluate_subgraph(
    selected_nodes: Iterable[Hashable], required_nodes: Iterable[Hashable]
) -> SetMetrics:
    return set_metrics(required_nodes, selected_nodes)


@dataclass(frozen=True, slots=True, kw_only=True)
class ClusteringMetrics:
    b_cubed_precision: float
    b_cubed_recall: float
    b_cubed_f1: float
    support: int


@dataclass(frozen=True, slots=True, kw_only=True)
class GraphContextMetrics:
    evidence_coverage: float
    temporal_precision: float
    connected_fraction: float
    selected_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class GroupCoverage:
    group: Hashable
    expected_count: int
    selected_count: int
    matched_count: int
    recall: float


@dataclass(frozen=True, slots=True, kw_only=True)
class GroupedCoverageMetrics:
    groups: tuple[GroupCoverage, ...]
    represented_group_fraction: float
    redundancy_rate: float


def evaluate_grouped_coverage(
    selected: Iterable[Hashable],
    expected: Iterable[Hashable],
    *,
    group: Callable[[Hashable], Hashable],
) -> GroupedCoverageMetrics:
    """Measure per-group recall and duplicate-group share separately."""

    selected_values = tuple(selected)
    selected_set = set(selected_values)
    expected_set = set(expected)
    groups = {group(item) for item in expected_set}
    entries: list[GroupCoverage] = []
    for group_id in sorted(groups, key=repr):
        expected_group = {item for item in expected_set if group(item) == group_id}
        selected_group = {item for item in selected_set if group(item) == group_id}
        matched = selected_group & expected_group
        entries.append(
            GroupCoverage(
                group=group_id,
                expected_count=len(expected_group),
                selected_count=len(selected_group),
                matched_count=len(matched),
                recall=len(matched) / len(expected_group),
            )
        )
    represented = sum(entry.matched_count > 0 for entry in entries)
    selected_groups = {group(item) for item in selected_values}
    redundancy = (
        1 - len(selected_groups) / len(selected_values) if selected_values else 0.0
    )
    return GroupedCoverageMetrics(
        groups=tuple(entries),
        represented_group_fraction=represented / len(entries) if entries else 1.0,
        redundancy_rate=redundancy,
    )


def evaluate_graph_context(
    selected_nodes: Iterable[Hashable],
    *,
    evidence_required: Iterable[Hashable],
    temporally_valid: Iterable[Hashable],
    edges: Iterable[tuple[Hashable, Hashable]],
) -> GraphContextMetrics:
    """Report independent context dimensions without combining their meaning."""

    selected = set(selected_nodes)
    required = set(evidence_required)
    valid = set(temporally_valid)
    coverage = len(selected & required) / len(required) if required else 1.0
    temporal = len(selected & valid) / len(selected) if selected else 1.0
    adjacency: dict[Hashable, set[Hashable]] = {node: set() for node in selected}
    for left, right in edges:
        if left in selected and right in selected:
            adjacency[left].add(right)
            adjacency[right].add(left)
    largest = 0
    remaining = set(selected)
    while remaining:
        frontier = [remaining.pop()]
        size = 0
        while frontier:
            node = frontier.pop()
            size += 1
            adjacent = adjacency[node] & remaining
            remaining.difference_update(adjacent)
            frontier.extend(adjacent)
        largest = max(largest, size)
    return GraphContextMetrics(
        evidence_coverage=coverage,
        temporal_precision=temporal,
        connected_fraction=largest / len(selected) if selected else 1.0,
        selected_count=len(selected),
    )


def evaluate_clustering(
    expected_clusters: Mapping[Hashable, Hashable],
    predicted_clusters: Mapping[Hashable, Hashable],
) -> ClusteringMetrics:
    if expected_clusters.keys() != predicted_clusters.keys():
        raise ValueError(
            "expected and predicted cluster assignments must have the same IDs"
        )
    ids = tuple(expected_clusters)
    if not ids:
        return ClusteringMetrics(
            b_cubed_precision=0.0, b_cubed_recall=0.0, b_cubed_f1=0.0, support=0
        )
    precision_values: list[float] = []
    recall_values: list[float] = []
    for item in ids:
        expected_group = {
            other
            for other in ids
            if expected_clusters[other] == expected_clusters[item]
        }
        predicted_group = {
            other
            for other in ids
            if predicted_clusters[other] == predicted_clusters[item]
        }
        overlap = len(expected_group & predicted_group)
        precision_values.append(overlap / len(predicted_group))
        recall_values.append(overlap / len(expected_group))
    precision = sum(precision_values) / len(ids)
    recall = sum(recall_values) / len(ids)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return ClusteringMetrics(
        b_cubed_precision=precision,
        b_cubed_recall=recall,
        b_cubed_f1=f1,
        support=len(ids),
    )
