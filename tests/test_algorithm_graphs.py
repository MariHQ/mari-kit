import pytest

from mari_components.algorithms.graph_retrieval import (
    TypedLink,
    UnionCandidate,
    expand_typed_links,
    hipporag_seed_weights,
    rank_candidate_union,
    rank_episode_mentions,
    rank_graph_distances,
    weighted_chunk_polling,
)
from mari_components.algorithms.graphs import (
    cohesive_subgraph,
    condense_graph,
    hierarchical_leiden_partition,
    louvain_partition,
    prize_collecting_forest,
    transitive_reduction_edges,
)


def test_pcst_crosses_zero_prize_bridge():
    pytest.importorskip("pcst_fast")
    result = prize_collecting_forest(
        {"seed": 0, "bridge": 0, "valuable": 10},
        [("seed", "bridge", 1), ("bridge", "valuable", 1)],
        root="seed",
    )
    assert set(result.nodes) == {"seed", "bridge", "valuable"}
    assert result.total_prize - result.total_cost == 8


def test_native_graph_choices():
    pytest.importorskip("networkx")
    nodes = ("a", "b", "c", "d")
    edges = [("a", "b", 1), ("b", "c", 1), ("a", "c", 1)]
    assert louvain_partition(nodes, edges) == (("a", "b", "c"), ("d",))
    assert set(cohesive_subgraph(nodes, edges, k=2)) == {"a", "b", "c"}
    assert set(cohesive_subgraph(nodes, edges, k=3, method="truss")) == {"a", "b", "c"}
    assert transitive_reduction_edges(nodes, edges) == (("a", "b", 1), ("b", "c", 1))
    condensed = condense_graph(nodes, [*edges, ("b", "a", 1)])
    assert ("a", "b") in condensed.components
    with pytest.raises(ValueError):
        transitive_reduction_edges(nodes, [("a", "b", 1), ("b", "a", 1)])
    pytest.importorskip("graspologic_native")
    communities = hierarchical_leiden_partition(nodes, edges, seed=42)
    assert {row.node for row in communities if row.final} == set(nodes)


def test_seed_construction_and_allowed_scope():
    result = hipporag_seed_weights(
        [("a", "b", 2), ("a", "c", 4)],
        entity_passage_counts={"a": 2},
        passage_scores={"p": 0.2, "q": 0.8, "secret": 100},
        allowed_nodes={"a", "b", "c", "p", "q"},
        link_top_k=2,
    )
    weights = {r.node: r for r in result}
    assert weights["c"].entity_weight == 4
    assert weights["b"].entity_weight == 2
    assert weights["q"].passage_weight == 0.05
    assert "secret" not in weights


def test_polling_redistributes_and_deduplicates_after_budget():
    result = weighted_chunk_polling([[], ["a", "b", "c"], ["d"]], maximum=4)
    assert len(result.chunks) == 4
    assert set(result.chunks) == {"a", "b", "c", "d"}
    duplicate = weighted_chunk_polling([["a"], ["a"]], maximum=2, deduplicate=True)
    assert duplicate.chunks == ("a",)


def test_typed_links_and_graph_reranking():
    result = expand_typed_links(
        {"s"},
        entity_members={"entity": ["s", "x", "secret"]},
        links=[
            TypedLink("s", "x", "semantic", 0.3),
            TypedLink("s", "x", "causal", 0.4),
        ],
        allowed_ids={"s", "x"},
    )
    assert result[0].item_id == "x"
    assert result[0].score == pytest.approx(0.7 + 0.46211715726)
    assert rank_graph_distances(["x", "s", "z"], {"s": 0, "x": 2})[0].item_id == "s"
    assert [
        r.item_id for r in rank_episode_mentions(["x", "y", "z"], {"x": 2, "y": 5})
    ] == ["y", "x", "z"]


def test_union_requires_common_space_or_shared_reranking():
    a = UnionCandidate("one", "a", 1, (1.0, 0.0), "space")
    b = UnionCandidate("two", "b", 1, (0.0, 1.0), "space")
    keys = {a.key, b.key}
    assert (
        rank_candidate_union(
            [a, b], allowed_keys=keys, query_vector=[1, 0], query_space="space"
        )[0].candidate
        == a
    )
    assert (
        rank_candidate_union(
            [a, b], allowed_keys=keys, union_scores={a.key: 0.1, b.key: 0.8}
        )[0].candidate
        == b
    )
    with pytest.raises(ValueError):
        rank_candidate_union(
            [a, b], allowed_keys=keys, query_vector=[1, 0], query_space="wrong"
        )
    assert (
        len(rank_candidate_union([a, b], allowed_keys={a.key}, union_scores={a.key: 1}))
        == 1
    )


def test_polling_maximum_is_parent_quota_not_global_cap():
    result = weighted_chunk_polling(
        [["a", "b", "c"], ["d", "e", "f"]], maximum=3, minimum=1
    )
    assert result.quotas == (3, 1)
    assert result.chunks == ("a", "b", "c", "d")
