from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from mari_components.evaluation import (
    evaluate_clustering,
    evaluate_link_prediction,
    evaluate_path,
    evaluate_subgraph,
)
from mari_components.graph import (
    GraphProjection,
    ProjectionEdge,
    TimeInterval,
    betweenness_centrality,
    bind_relation_evidence,
    bounded_seed_expansion,
    breadth_first,
    candidate_pairs,
    closeness_centrality,
    cluster_matches,
    connected_components,
    degree_centrality,
    directed_cycles,
    graph_diff,
    hits,
    inspect_graph_quality,
    interval_intersection,
    prize_guided_subgraph,
    propagated_taints,
    score_link_candidates,
    shortest_path,
    simrank_scores,
    temporal_join,
    to_graphml,
    to_json_ld,
    trace_lineage,
)


def adjacency(edges: tuple[tuple[str, str], ...]):
    def neighbors(node: str) -> tuple[str, ...]:
        return tuple(right for left, right in edges if left == node)

    return neighbors


def undirected(edges: tuple[tuple[str, str], ...]):
    def neighbors(node: str) -> tuple[str, ...]:
        return tuple(
            right if left == node else left
            for left, right in edges
            if left == node or right == node
        )

    return neighbors


def test_traversal_is_stable_bounded_and_authorized() -> None:
    graph = adjacency((("a", "c"), ("a", "b"), ("b", "d"), ("c", "d")))
    result = breadth_first(("a",), neighbors=graph, allowed=lambda node: node != "c")
    assert result.nodes == ("a", "b", "d")
    limited = breadth_first(("a",), neighbors=graph, max_nodes=2)
    assert limited.nodes == ("a", "b")
    assert limited.truncated


def test_weighted_shortest_path_and_validation() -> None:
    graph = adjacency((("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")))
    costs = {("a", "b"): 4, ("a", "c"): 1, ("b", "d"): 1, ("c", "d"): 1}
    result = shortest_path(
        "a", "d", neighbors=graph, edge_cost=lambda left, right: costs[(left, right)]
    )
    assert result.nodes == ("a", "c", "d")
    assert result.cost == 2
    with pytest.raises(ValueError, match="non-negative"):
        shortest_path("a", "d", neighbors=graph, edge_cost=lambda _a, _b: -1)


def test_connected_components() -> None:
    graph = undirected((("a", "b"), ("c", "d")))
    assert connected_components(("d", "c", "b", "a", "z"), neighbors=graph) == (
        ("a", "b"),
        ("c", "d"),
        ("z",),
    )


def test_cycles_and_centrality_are_callback_driven() -> None:
    directed = adjacency((("a", "b"), ("b", "c"), ("c", "a"), ("c", "d")))
    cycles = directed_cycles(("a", "b", "c", "d"), neighbors=directed)
    assert cycles.cycles == (("a", "b", "c"),)
    line = undirected((("a", "b"), ("b", "c")))
    assert degree_centrality(("a", "b", "c"), neighbors=line)[0] == ("b", 1.0)
    assert closeness_centrality(("a", "b", "c"), neighbors=line)[0][0] == "b"
    assert betweenness_centrality(("a", "b", "c"), neighbors=line)[0] == ("b", 1.0)
    hub_scores = dict(
        (node, (hub, authority))
        for node, hub, authority in hits(("a", "b", "c", "d"), successors=directed)
    )
    assert hub_scores["c"][0] > 0


def test_subgraph_selection_exposes_budget_and_objective() -> None:
    graph = undirected((("a", "b"), ("a", "c"), ("b", "d")))
    expanded = bounded_seed_expansion(
        seeds=("a",),
        neighbors=graph,
        score=lambda node: {"a": 1, "b": 3, "c": 2, "d": 4}[node],
        max_nodes=3,
        max_depth=2,
    )
    assert set(expanded.nodes) == {"a", "b", "c"}
    selected = prize_guided_subgraph(
        seeds=("a",),
        neighbors=graph,
        prize=lambda node: {"a": 2, "b": 3, "c": 0.25, "d": 2}[node],
        edge_cost=lambda _left, _right: 1,
        max_nodes=4,
    )
    assert set(selected.nodes) == {"a", "b", "d"}
    assert selected.total_prize == 7
    assert selected.total_cost == 2


def test_link_scores_are_explainable() -> None:
    graph = undirected((("a", "x"), ("a", "y"), ("b", "x"), ("b", "z"), ("x", "q")))
    jaccard = score_link_candidates(candidate_pairs=(("a", "b"),), neighbors=graph)
    assert jaccard[0].common_neighbors == ("x",)
    assert jaccard[0].score == pytest.approx(1 / 3)
    adamic = score_link_candidates(
        candidate_pairs=(("a", "b"),), neighbors=graph, method="adamic_adar"
    )
    assert adamic[0].score == pytest.approx(1 / 1.0986122886681098)
    simrank = simrank_scores(("a", "b", "x", "y"), incoming=graph, iterations=3)
    assert all(0 <= score <= 1 for _, _, score in simrank)


def test_graph_diff_and_quality_are_policy_neutral() -> None:
    diff = graph_diff(
        before_nodes=("a", "b"),
        before_edges=(("a", "b"),),
        after_nodes=("a", "c"),
        after_edges=(("a", "c"),),
    )
    assert diff.added_nodes == {"c"}
    assert diff.node_change_rate == 2 / 3
    report = inspect_graph_quality(
        nodes=("a", "b", "b-copy", "orphan"),
        edges=(("a", "b"), ("missing", "a"), ("b", "b")),
        fingerprint=lambda node: "b" if node.startswith("b") else node,
    )
    assert report.dangling_edges == (("missing", "a"),)
    assert report.orphan_nodes == ("b-copy", "orphan")
    assert report.duplicate_groups == (("b", "b-copy"),)


def test_blocking_and_clustering_return_proposals() -> None:
    entities = ("alice-1", "alice-2", "bob")
    pairs = candidate_pairs(
        entity_ids=entities, blocking_keys=lambda item: (item.split("-")[0],)
    )
    assert pairs == (("alice-1", "alice-2"),)
    result = cluster_matches(
        entity_ids=entities,
        candidate_pairs=pairs,
        score=lambda _left, _right: 0.95,
        threshold=0.9,
    )
    assert result.clusters == (("alice-1", "alice-2"), ("bob",))
    assert len(result.accepted_links) == 1
    bound = bind_relation_evidence(
        ("candidate", "unsupported"),
        resolve=lambda value: ("quote",) if value == "candidate" else (),
    )
    assert bound[0].accepted
    assert not bound[1].accepted


def test_temporal_join_uses_half_open_intervals() -> None:
    jan = TimeInterval(
        start=datetime(2026, 1, 1, tzinfo=UTC), end=datetime(2026, 2, 1, tzinfo=UTC)
    )
    feb = TimeInterval(
        start=datetime(2026, 2, 1, tzinfo=UTC), end=datetime(2026, 3, 1, tzinfo=UTC)
    )
    overlap = TimeInterval(
        start=datetime(2026, 1, 15, tzinfo=UTC), end=datetime(2026, 2, 15, tzinfo=UTC)
    )
    assert interval_intersection(jan, feb) is None
    assert interval_intersection(jan, overlap) == TimeInterval(
        start=datetime(2026, 1, 15, tzinfo=UTC),
        end=datetime(2026, 2, 1, tzinfo=UTC),
    )
    joined = temporal_join(
        (("p", jan),),
        (("p", overlap), ("p", feb)),
        left_key=lambda item: item[0],
        right_key=lambda item: item[0],
        left_interval=lambda item: item[1],
        right_interval=lambda item: item[1],
    )
    assert len(joined) == 1


def test_lineage_reports_cycles_and_propagates_taints() -> None:
    parents = {"summary": ("fact",), "fact": ("source",), "source": ("summary",)}
    trace = trace_lineage("summary", parents=parents.__getitem__)
    assert tuple(visit.artifact_id for visit in trace.visits) == (
        "summary",
        "fact",
        "source",
    )
    assert trace.cycle_edges == (("source", "summary"),)
    labels = {"summary": (), "fact": ("model_generated",), "source": ("untrusted",)}
    assert propagated_taints(
        "summary", parents=parents.__getitem__, taints=labels.__getitem__
    ) == (
        "model_generated",
        "untrusted",
    )


def test_interchange_is_deterministic_and_reports_losses() -> None:
    projection = GraphProjection(
        nodes=(("a&b", {"kind": "Person", "nested": {"x": 1}}), ("p", {})),
        edges=(ProjectionEdge(source="a&b", target="p", relation="uses"),),
    )
    graphml = to_graphml(projection)
    assert graphml.data == to_graphml(projection).data
    assert b"a&amp;b" in graphml.data
    assert graphml.report.losses == ("node:a&b:nested:nested_value",)
    json_ld = to_json_ld(projection)
    assert json.loads(json_ld.data)["@graph"][0]["@id"] == "a&b"


def test_graph_component_metrics_remain_separate() -> None:
    links = evaluate_link_prediction({"a": ("x", "b")}, {"a": ("b",)}, k=2)
    assert links.hits_at_k == 1
    assert links.mean_reciprocal_rank == 0.5
    subgraph = evaluate_subgraph(("a", "b"), ("a", "c"))
    assert subgraph.precision == subgraph.recall == 0.5
    clusters = evaluate_clustering(
        {"a": 1, "b": 1, "c": 2},
        {"a": 1, "b": 2, "c": 2},
    )
    assert 0 < clusters.b_cubed_f1 < 1
    path = evaluate_path(("a", "c", "b"), ("a", "b", "c"))
    assert path.exact_match is False
    assert path.node_precision == path.node_recall == 1
    assert path.edge_precision == path.edge_recall == 0
