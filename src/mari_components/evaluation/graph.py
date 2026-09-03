"""Component metrics for graph construction and selection."""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Mapping, Sequence
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
