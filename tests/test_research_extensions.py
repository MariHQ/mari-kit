from __future__ import annotations

import unittest

import numpy as np

from mari_components.knowledge import (
    MemorySignal,
    plan_note_evolution,
    rank_salient_memories,
)
from mari_components.retrieval import (
    CompressionSentence,
    CorrectiveAction,
    build_summary_tree,
    hypothetical_document_embedding,
    plan_active_retrieval,
    plan_corrective_retrieval,
    selective_compression,
    walk_summary_tree,
)
from mari_components.verification import (
    AnswerSource,
    EvidenceNote,
    decide_from_evidence_notes,
    score_self_rag_candidate,
)


class HydeTests(unittest.TestCase):
    def test_hypothetical_embeddings_form_normalized_weighted_centroid(self):
        vector = hypothetical_document_embedding(
            (np.array([1.0, 0.0]), np.array([0.0, 1.0])),
            weights=(3.0, 1.0),
        )
        np.testing.assert_allclose(np.linalg.norm(vector), 1.0)
        self.assertGreater(vector[0], vector[1])

    def test_zero_centroid_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-zero"):
            hypothetical_document_embedding(
                (np.array([1.0, 0.0]), np.array([-1.0, 0.0]))
            )


class RaptorAndMemWalkerTests(unittest.TestCase):
    def setUp(self):
        def cluster(nodes, _level):
            ids = [node.node_id for node in nodes]
            if len(ids) <= 2:
                return (tuple(ids),)
            return tuple(tuple(ids[index : index + 2]) for index in range(0, len(ids), 2))

        self.tree = build_summary_tree(
            {"a": "alpha", "b": "beta", "c": "gamma", "d": "delta"},
            cluster=cluster,
            summarize=lambda children, level: f"level {level}: "
            + " ".join(child.text for child in children),
        )

    def test_recursive_tree_retains_all_children_and_one_root(self):
        self.assertEqual(len(self.tree.nodes), 7)
        self.assertEqual(len(self.tree.root_ids), 1)
        self.assertEqual(max(node.level for node in self.tree.nodes), 2)

    def test_tree_walk_is_bounded_and_records_navigation(self):
        walk = walk_summary_tree(
            self.tree,
            lambda node: 1.0 if "delta" in node.text else 0.0,
            branch_factor=1,
            max_visits=3,
        )
        self.assertEqual(walk.leaf_ids, ("d",))
        self.assertEqual(len(walk.visited), 3)
        self.assertTrue(walk.exhausted)

    def test_clusters_must_be_a_reducing_partition(self):
        with self.assertRaisesRegex(ValueError, "partition"):
            build_summary_tree(
                {"a": "alpha", "b": "beta"},
                cluster=lambda _nodes, _level: (("a",),),
                summarize=lambda _children, _level: "summary",
            )


class CorrectiveAndActiveRetrievalTests(unittest.TestCase):
    def test_crag_selects_all_three_actions(self):
        self.assertEqual(
            plan_corrective_retrieval((0.9,)).action,
            CorrectiveAction.USE_RETRIEVED,
        )
        self.assertEqual(
            plan_corrective_retrieval((0.5,)).action,
            CorrectiveAction.COMBINE_WITH_EXTERNAL,
        )
        self.assertEqual(
            plan_corrective_retrieval((0.1,)).action,
            CorrectiveAction.REPLACE_WITH_EXTERNAL,
        )

    def test_flare_masks_low_confidence_tokens_and_skips_confident_text(self):
        query = plan_active_retrieval(
            ("The", "refund", "window", "is", "thirty", "days"),
            (0.99, 0.95, 0.9, 0.8, 0.1, 0.15),
            threshold=0.2,
        )
        self.assertIsNotNone(query)
        assert query is not None
        self.assertEqual(query.query, "The refund window is")
        self.assertEqual(query.low_confidence_positions, (4, 5))
        self.assertIsNone(plan_active_retrieval(("known",), (0.99,)))


class RecompTests(unittest.TestCase):
    def test_compression_chooses_density_but_restores_source_order(self):
        result = selective_compression(
            (
                CompressionSentence(
                    sentence_id="first", text="First.", token_count=4, relevance=0.8
                ),
                CompressionSentence(
                    sentence_id="middle", text="Middle.", token_count=4, relevance=0.2
                ),
                CompressionSentence(
                    sentence_id="last", text="Last.", token_count=2, relevance=0.7
                ),
            ),
            token_budget=6,
            relevance_threshold=0.5,
        )
        self.assertEqual(result.selected_ids, ("first", "last"))
        self.assertEqual(result.text, "First. Last.")
        self.assertEqual(result.excluded_ids, ("middle",))

    def test_irrelevant_input_produces_empty_augmentation(self):
        result = selective_compression(
            (
                CompressionSentence(
                    sentence_id="noise", text="Noise.", token_count=2, relevance=0.1
                ),
            ),
            token_budget=10,
            relevance_threshold=0.5,
        )
        self.assertEqual(result.text, "")


class AgenticMemoryTests(unittest.TestCase):
    def test_note_links_and_evolution_have_separate_thresholds(self):
        plan = plan_note_evolution(
            "new", {"close": 0.95, "related": 0.8, "noise": 0.1}
        )
        self.assertEqual(plan.link_ids, ("close", "related"))
        self.assertEqual(plan.evolution_ids, ("close",))

    def test_salience_exposes_normalized_components(self):
        hits = rank_salient_memories(
            (
                MemorySignal(
                    memory_id="recent", hours_since_access=0, importance=1, relevance=1
                ),
                MemorySignal(
                    memory_id="useful", hours_since_access=10, importance=10, relevance=10
                ),
            ),
            recency_weight=0.1,
            importance_weight=1,
            relevance_weight=1,
        )
        self.assertEqual(hits[0].memory_id, "useful")
        self.assertEqual(hits[0].importance, 1.0)
        self.assertEqual(hits[0].relevance, 1.0)


class ReflectionAndEvidenceNoteTests(unittest.TestCase):
    def test_self_rag_score_exposes_each_weighted_contribution(self):
        result = score_self_rag_candidate(
            generation_probability=0.2,
            retrieve_probability=0.8,
            relevance_probability=0.9,
            support_probability=0.7,
            utility=0.6,
        )
        self.assertTrue(result.retrieve)
        self.assertAlmostEqual(result.utility_contribution, 0.3)
        self.assertAlmostEqual(result.score, 2.1)

    def test_chain_of_note_prefers_supported_evidence_then_abstains(self):
        supported = decide_from_evidence_notes(
            (
                EvidenceNote(document_id="noise", relevant=False, supports_answer=False),
                EvidenceNote(document_id="source", relevant=True, supports_answer=True),
            ),
            parametric_knowledge_available=True,
        )
        self.assertEqual(supported.source, AnswerSource.RETRIEVED)
        self.assertEqual(supported.supporting_document_ids, ("source",))
        unknown = decide_from_evidence_notes(())
        self.assertEqual(unknown.source, AnswerSource.UNKNOWN)

    def test_chain_of_note_rejects_inconsistent_judgment(self):
        with self.assertRaisesRegex(ValueError, "must also be relevant"):
            decide_from_evidence_notes(
                (
                    EvidenceNote(
                        document_id="bad", relevant=False, supports_answer=True
                    ),
                )
            )


if __name__ == "__main__":
    unittest.main()
