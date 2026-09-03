from __future__ import annotations

import unittest

import numpy as np

from mari_components.retrieval import (
    SparseContradictionCandidate,
    hoyer_difference_sparsity,
    rank_sparse_contradictions,
    sparse_contradiction_score,
    sparse_contrastive_losses,
)
from mari_components.verification import (
    document_contradiction_rewards,
    reasoning_sentence_references,
    validate_document_contradiction,
)


class SparseCLTests(unittest.TestCase):
    def test_hoyer_matches_mit_overcomplete_reference_vectors(self):
        origin = np.zeros(3)
        self.assertAlmostEqual(
            hoyer_difference_sparsity(origin, np.array([1.0, 0.0, 0.0])),
            1.0,
        )
        self.assertAlmostEqual(
            hoyer_difference_sparsity(origin, np.array([1.0, 1.0, 1.0])),
            0.0,
        )

    def test_hoyer_sparsity_distinguishes_sparse_and_dense_differences(self):
        origin = np.zeros(4)
        self.assertAlmostEqual(
            hoyer_difference_sparsity(origin, np.array([1.0, 0.0, 0.0, 0.0])),
            1.0,
        )
        self.assertAlmostEqual(
            hoyer_difference_sparsity(origin, np.ones(4)),
            0.0,
        )
        self.assertEqual(hoyer_difference_sparsity(origin, origin), 0.0)

    def test_combined_score_exposes_cosine_and_hoyer_components(self):
        result = sparse_contradiction_score(
            np.array([1.0, 0.0]),
            np.array([1.0, 0.0]),
            np.zeros(4),
            np.array([1.0, 0.0, 0.0, 0.0]),
            alpha=0.5,
        )
        self.assertAlmostEqual(result.cosine_similarity, 1.0)
        self.assertAlmostEqual(result.difference_sparsity, 1.0)
        self.assertAlmostEqual(result.score, 1.5)

    def test_cosine_prefilter_then_sparse_rerank_is_stable_and_authorized(self):
        candidates = (
            SparseContradictionCandidate(
                passage_id="contradiction",
                similarity_embedding=np.array([0.9, 0.1]),
                sparse_embedding=np.array([1.0, 0.0, 0.0, 0.0]),
            ),
            SparseContradictionCandidate(
                passage_id="paraphrase",
                similarity_embedding=np.array([1.0, 0.0]),
                sparse_embedding=np.ones(4),
            ),
        )
        hits = rank_sparse_contradictions(
            np.array([1.0, 0.0]),
            np.zeros(4),
            candidates,
            alpha=1.0,
            limit=2,
        )
        self.assertEqual([hit.passage_id for hit in hits], ["contradiction", "paraphrase"])
        self.assertEqual([hit.rank for hit in hits], [1, 2])

        allowed = rank_sparse_contradictions(
            np.array([1.0, 0.0]),
            np.zeros(4),
            candidates,
            alpha=1.0,
            limit=1,
            allowed_passage_ids={"paraphrase"},
        )
        self.assertEqual(tuple(hit.passage_id for hit in allowed), ("paraphrase",))

    def test_contrastive_objective_rewards_sparse_positive_difference(self):
        good = sparse_contrastive_losses(
            (np.zeros(4),),
            (np.array([1.0, 0.0, 0.0, 0.0]),),
            (np.ones(4),),
            temperature=0.1,
        )
        reversed_pairs = sparse_contrastive_losses(
            (np.zeros(4),),
            (np.ones(4),),
            (np.array([1.0, 0.0, 0.0, 0.0]),),
            temperature=0.1,
        )
        self.assertLess(float(good[0]), float(reversed_pairs[0]))

    def test_sparsecl_rejects_invalid_dimensions_and_limits(self):
        with self.assertRaisesRegex(ValueError, "at least two"):
            hoyer_difference_sparsity(np.array([1.0]), np.array([0.0]))
        with self.assertRaisesRegex(ValueError, "at least limit"):
            rank_sparse_contradictions(
                np.ones(2), np.ones(2), (), alpha=1.0, limit=2, candidate_limit=1
            )


class DocumentSelfContradictionTests(unittest.TestCase):
    def test_reference_coverage_matches_rrc_dscd_inclusive_range_fixture(self):
        assessment = validate_document_contradiction(
            sentence_count=8,
            judgment=False,
            reasoning="Review [1], [3-5], and [3] again.",
        )
        self.assertEqual(assessment.reasoning_sentence_ids, (1, 3, 4, 5))
        self.assertEqual(assessment.reference_coverage, 0.5)

    def test_reasoning_references_expand_all_supported_span_forms(self):
        self.assertEqual(
            reasoning_sentence_references(
                "Compare [1], [3-4], and [6]-[7].", sentence_count=7
            ),
            (1, 3, 4, 6, 7),
        )

    def test_positive_assessment_localizes_evidence_and_scores_rewards(self):
        assessment = validate_document_contradiction(
            sentence_count=5,
            judgment=True,
            evidence_sentence_ids=(2, 4),
            reasoning="Sentence [1-3] establishes the count; compare [5].",
        )
        rewards = document_contradiction_rewards(
            assessment,
            expected_judgment=True,
            gold_evidence_sentence_ids=(2, 3),
            format_valid=True,
        )
        self.assertAlmostEqual(assessment.reference_coverage, 0.8)
        self.assertAlmostEqual(rewards.accuracy, 1.5)
        self.assertEqual(rewards.reference_coverage, 0.8)
        self.assertEqual(rewards.format, 1.0)

    def test_correct_judgment_without_evidence_hit_is_penalized(self):
        assessment = validate_document_contradiction(
            sentence_count=4,
            judgment=True,
            evidence_sentence_ids=(4,),
            reasoning="I considered [4].",
        )
        rewards = document_contradiction_rewards(
            assessment,
            expected_judgment=True,
            gold_evidence_sentence_ids=(1, 2),
            format_valid=True,
        )
        self.assertEqual(rewards.accuracy, -1.0)

    def test_negative_judgment_uses_binary_accuracy_reward(self):
        assessment = validate_document_contradiction(
            sentence_count=3, judgment=False, reasoning="Reviewed [1-3]."
        )
        rewards = document_contradiction_rewards(
            assessment,
            expected_judgment=False,
            format_valid=False,
        )
        self.assertEqual(rewards.accuracy, 1.0)
        self.assertEqual(rewards.reference_coverage, 1.0)
        self.assertEqual(rewards.format, 0.0)

    def test_invalid_evidence_and_references_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "requires evidence"):
            validate_document_contradiction(sentence_count=2, judgment=True)
        with self.assertRaisesRegex(ValueError, "outside"):
            validate_document_contradiction(
                sentence_count=2,
                judgment=True,
                evidence_sentence_ids=(1,),
                reasoning="See [3].",
            )
        with self.assertRaisesRegex(ValueError, "integer"):
            validate_document_contradiction(
                sentence_count=2,
                judgment=True,
                evidence_sentence_ids=(1.5,),  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
