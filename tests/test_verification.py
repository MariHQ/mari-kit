from __future__ import annotations

import unittest

from mari_components import Evidence, FactCandidate
from mari_components.knowledge import FactAssessment
from mari_components.verification import (
    best_of_n,
    harmonic_score,
    score_grounded,
    select_best,
    verdict_consensus,
)


class VerificationTests(unittest.TestCase):
    def evidence(self, document_id: str = "docs/one") -> Evidence:
        return Evidence(
            document_id=document_id,
            revision="v1",
            quote="Retention is 30 days.",
        )

    def assessment(self, verdict: str, document_id: str = "docs/one") -> FactAssessment:
        evidence = () if verdict == "uncertain" else (self.evidence(document_id),)
        return FactAssessment(
            "Retention is 30 days.",
            verdict,
            "Checked.",
            0.9 if evidence else 0.0,
            evidence,
        )

    def test_harmonic_score_clamps_inputs(self):
        self.assertEqual(harmonic_score(0, 1), 0)
        self.assertEqual(harmonic_score(2, 1), 1)
        self.assertAlmostEqual(harmonic_score(0.5, 1), 2 / 3)

    def test_grounded_score_retains_each_axis(self):
        candidate = FactCandidate(
            claim="Retention is 30 days.",
            evidence=(self.evidence(), self.evidence("docs/two")),
            grounding_coverage=1.0,
        )
        result = score_grounded(candidate, required_ideas=("retention", "30 days"))
        self.assertEqual(result.groundedness, 1)
        self.assertEqual(result.completeness, 1)
        self.assertEqual(result.corroboration, 1)
        self.assertEqual(result.score, 1)

    def test_best_of_n_is_stable_auditable_and_can_stop_early(self):
        result = select_best(iter([0.2, 0.9, 1.0]), float, threshold=0.8)
        self.assertEqual(result.selected, 0.9)
        self.assertEqual(result.selected_index, 1)
        self.assertEqual(result.selected_attempt.candidate, 0.9)
        self.assertEqual(len(result.attempts), 2)
        self.assertTrue(result.stopped_early)

    def test_consensus_weights_evidence_and_abstains_on_a_tie(self):
        supported = self.assessment("supported")
        contradicted = self.assessment("contradicted", "docs/two")
        tied = verdict_consensus((supported, contradicted))
        self.assertEqual(tied.verdict, "uncertain")
        self.assertEqual(tied.evidence, ())

        agreed = verdict_consensus(
            (supported, contradicted), weights=(2.0, 1.0), minimum_agreement=0.6
        )
        self.assertEqual(agreed.verdict, "supported")
        self.assertEqual(agreed.evidence, supported.evidence)
        self.assertAlmostEqual(agreed.agreement, 0.6667, places=4)

    def test_best_of_n_generates_parses_and_scores_candidates(self):
        values = iter(["bad", "0.2", "0.95", "1.0"])

        result = best_of_n(
            lambda: next(values),
            float,
            float,
            attempts=3,
            threshold=0.9,
        )

        self.assertEqual(result.selected, 0.95)
        self.assertTrue(result.stopped_early)
        self.assertEqual(len(result.attempts), 2)
        self.assertEqual(result.failures[0].error_type, "ValueError")
        self.assertEqual(result.failures[0].index, 0)


if __name__ == "__main__":
    unittest.main()
