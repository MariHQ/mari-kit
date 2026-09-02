from __future__ import annotations

import unittest

from mari_components.retrieval import (
    maximal_marginal_relevance,
    personalized_pagerank,
    project_graph_scores,
    reciprocal_rank_fusion,
)


class RankFusionTests(unittest.TestCase):
    def test_rrf_accumulates_sources_and_ignores_per_source_duplicates(self):
        hits = reciprocal_rank_fusion(
            {
                "dense": ("a", "b", "a"),
                "lexical": ("b", "c", "a"),
            },
            rank_constant=10,
        )
        self.assertEqual([hit.document_id for hit in hits], ["b", "a", "c"])
        self.assertEqual(len(hits[0].contributions), 2)
        self.assertEqual(hits[0].contributions[0].rank, 2)

    def test_rrf_filters_before_scoring_and_exposes_weighted_contributions(self):
        hits = reciprocal_rank_fusion(
            {"dense": ("secret", "public"), "lexical": ("public",)},
            weights={"dense": 2.0, "lexical": 1.0},
            eligible=lambda document_id: document_id == "public",
        )
        self.assertEqual([hit.document_id for hit in hits], ["public"])
        self.assertEqual([row.rank for row in hits[0].contributions], [2, 1])

    def test_mmr_trades_redundancy_for_coverage(self):
        similarities = {
            frozenset(("refund-a", "refund-b")): 0.99,
            frozenset(("refund-a", "deployment")): 0.05,
            frozenset(("refund-b", "deployment")): 0.05,
        }
        hits = maximal_marginal_relevance(
            {"refund-a": 1.0, "refund-b": 0.98, "deployment": 0.75},
            lambda left, right: similarities[frozenset((left, right))],
            limit=2,
            relevance_weight=0.5,
        )
        self.assertEqual([hit.document_id for hit in hits], ["refund-a", "deployment"])
        self.assertEqual(hits[0].redundancy, 0.0)


class GraphRetrievalTests(unittest.TestCase):
    def test_pagerank_activates_a_multi_hop_neighbor_and_projects_passages(self):
        graph = {
            "stanford": {"thomas": 1.0},
            "thomas": {"alzheimer": 1.0},
            "alzheimer": {"thomas": 1.0},
        }
        result = personalized_pagerank(
            graph,
            {"stanford": 1.0, "alzheimer": 1.0},
            damping=0.85,
        )
        self.assertTrue(result.converged)
        scores = {hit.node_id: hit.score for hit in result.hits}
        self.assertGreater(scores["thomas"], scores["stanford"])
        passages = project_graph_scores(
            result.hits,
            {
                "stanford": {"passage-1": 1.0},
                "thomas": {"passage-2": 2.0},
                "alzheimer": {"passage-2": 1.0},
            },
        )
        self.assertEqual(passages[0].node_id, "passage-2")

    def test_allowed_nodes_are_removed_before_propagation(self):
        result = personalized_pagerank(
            {"allowed": {"forbidden": 100.0, "neighbor": 1.0}},
            {"allowed": 1.0},
            allowed_node_ids={"allowed", "neighbor"},
        )
        self.assertEqual({hit.node_id for hit in result.hits}, {"allowed", "neighbor"})
        self.assertAlmostEqual(sum(hit.score for hit in result.hits), 1.0)

    def test_no_allowed_seed_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "allowed seed"):
            personalized_pagerank(
                {"a": {"b": 1.0}},
                {"a": 1.0},
                allowed_node_ids={"b"},
            )


if __name__ == "__main__":
    unittest.main()
