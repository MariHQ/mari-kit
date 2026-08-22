from __future__ import annotations

import unittest

from mari_components import Evidence, KnowledgeDocument
from mari_components.errors import MalformedModelOutput
from mari_components.knowledge import (
    AnswerDisposition,
    FreshnessStatus,
    TagAssignments,
    TagDefinition,
    assess_freshness,
    assign_tags,
    extract_explicit_links,
    grounding_coverage,
    parse_answer,
    parse_answer_candidates,
    parse_claim_assessments,
    parse_decisions,
    parse_digest,
    parse_facts,
    parse_glossary,
    parse_refinement,
    search_weight,
)


class KnowledgeRecipeTests(unittest.TestCase):
    def setUp(self):
        self.document = KnowledgeDocument(
            source_id="docs",
            external_id="1",
            title="Retention",
            body="Retention is 30 days.",
            revision="v1",
        )

    def test_links_resolve_repo_root_extension_and_readme(self):
        paths = {"guide.md": "2", "topic/README.md": "3"}
        links = extract_explicit_links(
            "1",
            "docs/start.md",
            "[guide](/guide) [topic](../topic)",
            paths,
        )
        self.assertEqual({link.target_id for link in links}, {"2", "3"})

    def evidence(self):
        return [{"document_id": "docs/1", "quote": "Retention is 30 days."}]

    def test_fact_extract_and_check_preserve_evidence(self):
        facts = parse_facts(
            [self.document],
            {
                "facts": [
                    {
                        "claim": "Retention is 30 days.",
                        "confidence": 0,
                        "evidence": self.evidence(),
                    }
                ]
            },
        )
        self.assertEqual(facts[0].evidence[0].revision, "v1")
        self.assertEqual(
            (facts[0].evidence[0].start, facts[0].evidence[0].end),
            (0, len("Retention is 30 days.")),
        )
        self.assertEqual(facts[0].grounding_coverage, 0.9)
        checked = parse_claim_assessments(
            [facts[0].claim],
            [self.document],
            {
                "assessments": [
                    {
                        "claim": facts[0].claim,
                        "verdict": "supported",
                        "explanation": "Direct",
                        "confidence": 0,
                        "evidence": self.evidence(),
                    }
                ]
            },
        )
        self.assertEqual(checked[0].verdict, "supported")
        self.assertEqual(checked[0].grounding_coverage, 0.9)

    def test_model_confidence_is_ignored_and_evidence_score_is_reproducible(self):
        def extract(model_confidence):
            return parse_facts(
                [self.document],
                {
                    "facts": [
                        {
                            "claim": "Retention is 30 days.",
                            "confidence": model_confidence,
                            "evidence": self.evidence(),
                        }
                    ],
                },
            )[0].grounding_coverage

        self.assertEqual(extract(-100), extract(100))
        self.assertEqual(extract("not a number"), 0.9)

    def test_grounding_coverage_rewards_independent_corroboration(self):
        text = "Retention is 30 days."
        first = Evidence(document_id="docs/1", revision="v1", quote=text)
        second = Evidence(document_id="docs/2", revision="v1", quote=text)
        self.assertEqual(grounding_coverage(text, ()), 0)
        self.assertEqual(grounding_coverage(text, (first,)), 0.9)
        self.assertEqual(grounding_coverage(text, (first, second)), 1)
        self.assertEqual(grounding_coverage(text, (first, second)), 1)

    def test_revision_change_invalidates_evidence_backed_artifact(self):
        evidence = (
            Evidence(
                document_id="docs/1", revision="v1", quote="Retention is 30 days."
            ),
        )
        current = assess_freshness(evidence, {"docs/1": "v1"})
        stale = assess_freshness(evidence, {"docs/1": "v2"})
        missing = assess_freshness(evidence, {})
        self.assertEqual(current.status, FreshnessStatus.CURRENT)
        self.assertTrue(current.reusable)
        self.assertEqual(stale.status, FreshnessStatus.STALE)
        self.assertFalse(stale.reusable)
        self.assertEqual(stale.changes[0].current_revision, "v2")
        self.assertEqual(missing.status, FreshnessStatus.MISSING)

    def test_unknown_evidence_fails_without_fallback(self):
        with self.assertRaises(MalformedModelOutput):
            parse_facts(
                [self.document],
                {
                    "facts": [
                        {
                            "claim": "x",
                            "evidence": [{"document_id": "other", "quote": "x"}],
                        }
                    ]
                },
            )
        with self.assertRaises(MalformedModelOutput):
            parse_facts(
                [self.document],
                {
                    "facts": [
                        {
                            "claim": "x",
                            "evidence": [
                                {"document_id": "docs/1", "quote": "invented quote"}
                            ],
                        }
                    ]
                },
            )

    def test_decisions_glossary_and_answers(self):
        decision = parse_decisions(
            [self.document],
            {"decisions": [{"statement": "Keep 30 days", "evidence": self.evidence()}]},
        )[0]
        glossary = parse_glossary(
            [self.document],
            {
                "terms": [
                    {
                        "term": "Retention",
                        "definition": "Storage period",
                        "aliases": [],
                        "evidence": self.evidence(),
                    }
                ]
            },
        )[0]
        mined = parse_answer_candidates(
            [self.document],
            {
                "answers": [
                    {
                        "question": "How long?",
                        "answer": "30 days",
                        "evidence": self.evidence(),
                    }
                ]
            },
        )[0]
        grounded = parse_answer(
            "How long?",
            [self.document],
            {"answer": "30 days", "evidence": self.evidence()},
        )
        self.assertEqual(
            (decision.statement, glossary.term, mined.answer, grounded.answer),
            ("Keep 30 days", "Retention", "30 days", "30 days"),
        )
        self.assertEqual(
            (mined.grounding_coverage, grounded.grounding_coverage), (0.9, 0.9)
        )
        self.assertEqual(grounded.disposition, AnswerDisposition.GROUNDED)

    def test_evidence_free_answer_is_explicitly_insufficient(self):
        answer = parse_answer(
            "Unknown?",
            [self.document],
            {
                "answer": "The supplied knowledge does not say.",
                "disposition": "insufficient_evidence",
                "evidence": [],
            },
        )
        self.assertEqual(answer.disposition, AnswerDisposition.INSUFFICIENT_EVIDENCE)
        self.assertEqual(answer.grounding_coverage, 0)

    def test_workspace_tags_validate_assignment_and_drive_search_weight(self):
        definitions = {
            "canonical": TagDefinition(
                key="canonical",
                label="Canonical",
                kind="canonical",
                search_weight=2.0,
                behaviors=("Boosts search", "Wins conflicts"),
            ),
            "stale": TagDefinition(
                key="stale",
                label="Stale",
                kind="stale",
                search_weight=0.5,
            ),
        }
        assignments = assign_tags(
            TagAssignments(),
            self.document.document_id,
            definitions,
            add=("Canonical",),
        )
        self.assertEqual(
            assignments.tags_for(self.document.document_id), frozenset({"canonical"})
        )
        self.assertEqual(
            search_weight(self.document.document_id, assignments, definitions), 2.0
        )
        with self.assertRaises(KeyError):
            assign_tags(
                assignments,
                self.document.document_id,
                definitions,
                add=("undefined",),
            )

    def test_refinement_requires_exact_substrings(self):
        edits = parse_refinement(
            self.document,
            {
                "edits": [
                    {
                        "original": "Retention is 30 days.",
                        "replacement": "We keep data for 30 days.",
                        "reason": "Plain language",
                    }
                ]
            },
        )
        self.assertEqual(edits[0].replacement, "We keep data for 30 days.")
        with self.assertRaises(MalformedModelOutput):
            parse_refinement(
                self.document,
                {
                    "edits": [
                        {
                            "original": "Invented text",
                            "replacement": "x",
                            "reason": "y",
                        }
                    ]
                },
            )

    def test_digest_topics_are_structured_and_evidence_linked(self):
        digest = parse_digest(
            [self.document],
            {
                "summary": "Retention changed.",
                "topics": [
                    {
                        "title": "Retention",
                        "summary": "Thirty days.",
                        "evidence": self.evidence(),
                    }
                ],
                "evidence": self.evidence(),
            },
        )
        self.assertEqual(digest.topics[0].evidence[0].document_id, "docs/1")


if __name__ == "__main__":
    unittest.main()
