from __future__ import annotations

import unittest

from mari_components import Evidence, KnowledgeDocument
from mari_components.errors import MalformedModelOutput
from mari_components.knowledge import (
    ApprovalPolicy,
    ReviewItem,
    answer_question,
    check_claims,
    evidence_confidence,
    evaluate_approval,
    extract_decisions,
    extract_explicit_links,
    extract_facts,
    harvest_glossary,
    mine_answers,
    refine_document,
    summarize_digest,
)


class KnowledgeRecipeTests(unittest.TestCase):
    def setUp(self):
        self.document = KnowledgeDocument("doc:1", "Retention", "Retention is 30 days.", revision="v1")

    def generator(self, value):
        return lambda _prompt, _version: value

    def test_links_resolve_repo_root_extension_and_readme(self):
        paths = {"guide.md": "2", "topic/README.md": "3"}
        links = extract_explicit_links(
            "1", "docs/start.md", "[guide](/guide) [topic](../topic)", paths,
        )
        self.assertEqual({link.target_id for link in links}, {"2", "3"})

    def evidence(self):
        return [{"document_id": "doc:1", "quote": "Retention is 30 days."}]

    def test_fact_extract_and_check_preserve_evidence(self):
        facts = extract_facts([self.document], generate_json=self.generator({"facts": [{"claim": "Retention is 30 days.", "confidence": 0, "evidence": self.evidence()}]}))
        self.assertEqual(facts[0].evidence[0].revision, "v1")
        self.assertEqual(facts[0].confidence, .9)
        checked = check_claims([facts[0].claim], [self.document], generate_json=self.generator({"assessments": [{"claim": facts[0].claim, "verdict": "supported", "explanation": "Direct", "confidence": 0, "evidence": self.evidence()}]}))
        self.assertEqual(checked[0].verdict, "supported")
        self.assertEqual(checked[0].confidence, .9)

    def test_model_confidence_is_ignored_and_evidence_score_is_reproducible(self):
        def extract(model_confidence):
            return extract_facts([self.document], generate_json=self.generator({
                "facts": [{
                    "claim": "Retention is 30 days.",
                    "confidence": model_confidence,
                    "evidence": self.evidence(),
                }],
            }))[0].confidence

        self.assertEqual(extract(-100), extract(100))
        self.assertEqual(extract("not a number"), .9)

    def test_evidence_confidence_rewards_independent_corroboration(self):
        text = "Retention is 30 days."
        first = Evidence("doc:1", quote=text)
        second = Evidence("doc:2", quote=text)
        self.assertEqual(evidence_confidence(text, ()), 0)
        self.assertEqual(evidence_confidence(text, (first,)), .9)
        self.assertEqual(evidence_confidence(text, (first, second)), 1)

    def test_unknown_evidence_fails_without_fallback(self):
        with self.assertRaises(MalformedModelOutput):
            extract_facts([self.document], generate_json=self.generator({"facts": [{"claim": "x", "evidence": [{"document_id": "other", "quote": "x"}]}]}))
        with self.assertRaises(MalformedModelOutput):
            extract_facts([self.document], generate_json=self.generator({"facts": [{"claim": "x", "evidence": [{"document_id": "doc:1", "quote": "invented quote"}]}]}))

    def test_decisions_glossary_and_answers(self):
        decision = extract_decisions([self.document], generate_json=self.generator({"decisions": [{"statement": "Keep 30 days", "evidence": self.evidence()}]}))[0]
        glossary = harvest_glossary([self.document], generate_json=self.generator({"terms": [{"term": "Retention", "definition": "Storage period", "aliases": [], "evidence": self.evidence()}]}))[0]
        mined = mine_answers([self.document], generate_json=self.generator({"answers": [{"question": "How long?", "answer": "30 days", "evidence": self.evidence()}]}))[0]
        grounded = answer_question("How long?", [self.document], generate_json=self.generator({"answer": "30 days", "evidence": self.evidence()}))
        self.assertEqual((decision.statement, glossary.term, mined.answer, grounded.answer), ("Keep 30 days", "Retention", "30 days", "30 days"))
        self.assertEqual((mined.confidence, grounded.confidence), (.9, .9))

    def test_approval_uses_immutable_ids(self):
        item = ReviewItem("fact:1", "fact", "user:1", .95, 2, True)
        self.assertEqual(evaluate_approval(item, "user:1").outcome, "deny")
        self.assertEqual(evaluate_approval(item, "user:2", ApprovalPolicy()).outcome, "allow")

    def test_refinement_requires_exact_substrings(self):
        edits = refine_document(
            self.document,
            "Use plain language",
            generate_json=self.generator({"edits": [{
                "original": "Retention is 30 days.",
                "replacement": "We keep data for 30 days.",
                "reason": "Plain language",
            }]}),
        )
        self.assertEqual(edits[0].replacement, "We keep data for 30 days.")
        with self.assertRaises(MalformedModelOutput):
            refine_document(
                self.document,
                "Rewrite",
                generate_json=self.generator({"edits": [{
                    "original": "Invented text", "replacement": "x", "reason": "y",
                }]}),
            )

    def test_digest_topics_are_structured_and_evidence_linked(self):
        digest = summarize_digest(
            [self.document],
            generate_json=self.generator({
                "summary": "Retention changed.",
                "topics": [{"title": "Retention", "summary": "Thirty days.", "evidence": self.evidence()}],
                "evidence": self.evidence(),
            }),
        )
        self.assertEqual(digest.topics[0].evidence[0].document_id, "doc:1")


if __name__ == "__main__":
    unittest.main()
