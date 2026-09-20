"""Behavioral tests for the customer support company brain example."""

from __future__ import annotations

import json
import unittest

from examples.company_brains import support
from mari_kit import KnowledgeDocument, Principal
from mari_kit.errors import MalformedModelOutput
from mari_kit.knowledge import parse_answer, section_revisions
from mari_kit.trajectories import (
    ReviewedWorkflow,
    WorkflowAction,
    WorkflowPolicy,
    build_reviewed_workflow_index,
    decide_reviewed_workflow,
    match_cached_response,
    match_reviewed_workflow,
    start_speculative_retrieval,
)


class SupportCompanyBrainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = support.run()

    def test_run_is_credential_free_and_json_serializable(self) -> None:
        self.assertEqual(self.result["company"], "customer-support")
        self.assertTrue(self.result["credential_free"])
        self.assertEqual(self.result["policy"]["cache_threshold"], 0.97)
        self.assertIsInstance(json.dumps(self.result), str)

    def test_valid_reuse_serves_the_reviewed_answer(self) -> None:
        reuse = self.result["valid_reuse"]
        self.assertEqual(reuse["action"], "cached_response")
        self.assertEqual(reuse["reason"], "exact_fresh_cache")
        self.assertEqual(reuse["workflow_id"], "support-refund")
        self.assertTrue(reuse["cache_reusable"])
        self.assertTrue(reuse["served_reviewed_answer"])
        self.assertGreaterEqual(
            reuse["score"], self.result["policy"]["cache_threshold"]
        )
        self.assertIn("30 days", reuse["cached_answer"])

    def test_changed_cited_source_invalidates_only_that_answer(self) -> None:
        changed = self.result["changed_source"]
        self.assertEqual(changed["action"], "speculative_retrieval")
        self.assertEqual(changed["reason"], "stale_dependency")
        self.assertIsNone(changed["cached_answer"])
        self.assertIn("workflow:support-refund", changed["impacted_artifacts"])
        self.assertTrue(changed["shipping_reused_after_change"])
        self.assertEqual(
            changed["changed_context_voice_action"], "speculative_retrieval"
        )

    def test_unrelated_section_edit_preserves_cache_with_section_revisions(
        self,
    ) -> None:
        edit = self.result["unrelated_source_edit"]
        self.assertEqual(edit["with_section_revisions"], "cached_response")
        self.assertEqual(edit["with_section_revisions_reason"], "exact_fresh_cache")
        self.assertEqual(edit["whole_document_fallback"], "speculative_retrieval")
        self.assertEqual(edit["whole_document_fallback_reason"], "stale_dependency")

    def test_relevant_new_document_requires_review_then_can_be_cleared(self) -> None:
        new = self.result["relevant_new_document"]
        self.assertEqual(new["unresolved"]["action"], "speculative_retrieval")
        self.assertEqual(
            new["unresolved"]["reason"], "relevant_document_needs_impact_review"
        )
        self.assertIn(
            new["new_document_id"],
            new["unresolved"]["documents_needing_impact_review"],
        )
        self.assertIsNone(new["unresolved"]["cached_answer"])
        self.assertEqual(new["nonimpacting"]["action"], "cached_response")
        self.assertEqual(new["impacting"]["action"], "speculative_retrieval")
        self.assertEqual(
            new["impacting"]["reason"], "relevant_document_impacts_response"
        )

    def test_revoked_access_never_serves_a_cached_answer(self) -> None:
        revoked = self.result["revoked_access"]
        self.assertNotIn(
            revoked["restricted_document_id"], revoked["allowed_document_ids"]
        )
        self.assertEqual(revoked["action"], "llm")
        self.assertEqual(revoked["reason"], "no_intent_match")
        self.assertIsNone(revoked["cached_answer"])
        self.assertFalse(revoked["cached_answer_returned"])
        self.assertFalse(revoked["cache_reusable"])

    def test_unanswered_question_routes_to_host_llm(self) -> None:
        unanswered = self.result["unanswered_question"]
        self.assertEqual(unanswered["action"], "llm")
        self.assertEqual(unanswered["reason"], "no_intent_match")
        self.assertIsNone(unanswered["cached_answer"])

    def test_cold_intent_requests_speculative_retrieval(self) -> None:
        cold = self.result["cold_reviewed_intent"]
        self.assertEqual(cold["action"], "speculative_retrieval")
        self.assertEqual(cold["reason"], "no_cached_response")
        self.assertIsNone(cold["cached_answer"])

    def test_near_miss_stays_below_cache_gate(self) -> None:
        near = self.result["below_cache_threshold"]
        policy = self.result["policy"]
        self.assertEqual(near["action"], "speculative_retrieval")
        self.assertEqual(near["reason"], "below_cache_threshold")
        self.assertGreaterEqual(near["score"], policy["speculation_threshold"])
        self.assertLess(near["score"], policy["cache_threshold"])

    def test_speculative_read_starts_before_await(self) -> None:
        speculative = self.result["speculative_retrieval"]
        self.assertTrue(speculative["started_before_await"])
        self.assertIn(
            support.ENTERPRISE_REFUND_POLICY.document_id,
            speculative["read_document_ids"],
        )


class HostBoundaryFailureTests(unittest.TestCase):
    def test_revoked_principal_cannot_see_restricted_document(self) -> None:
        allowed = support.allowed_document_ids(
            (Principal(kind="team", identifier="support"),)
        )
        self.assertNotIn(support.ENTERPRISE_REFUND_POLICY.document_id, allowed)
        self.assertIn(support.SHIPPING_POLICY.document_id, allowed)

    def test_speculative_retrieval_rejects_cached_decisions(self) -> None:
        revisions = {
            document.document_id: document.revision for document in support.DOCUMENTS
        }
        decision = decide_reviewed_workflow(
            (support.REFUND_INTENT,),
            support.WORKFLOW_INDEX,
            revisions,
            current_section_revisions=section_revisions(support.DOCUMENTS),
            allowed_document_ids=support.allowed_document_ids(
                (
                    Principal(kind="team", identifier="support"),
                    Principal(kind="team", identifier="enterprise-support"),
                )
            ),
            policy=support.POLICY,
        )
        self.assertIs(decision.action, WorkflowAction.CACHED_RESPONSE)

        async def retrieve(document_ids: tuple[str, ...]) -> tuple[str, ...]:
            return document_ids

        with self.assertRaisesRegex(
            ValueError, "does not permit speculative retrieval"
        ):
            start_speculative_retrieval(decision, retrieve)

    def test_policy_rejects_inverted_thresholds(self) -> None:
        with self.assertRaises(ValueError):
            WorkflowPolicy(speculation_threshold=0.8, cache_threshold=0.5)
        with self.assertRaises(ValueError):
            WorkflowPolicy(speculation_threshold=-2.0)

    def test_workflow_rejects_dependency_outside_document_ids(self) -> None:
        with self.assertRaises(ValueError):
            ReviewedWorkflow(
                identifier="bad-workflow",
                name="Bad workflow",
                match_vectors=((1.0, 0.0),),
                document_ids=("support:kb/unrelated",),
                cached_answer=support.REVIEWED_REFUND_ANSWER,
            )

    def test_parse_answer_rejects_an_unverifiable_quote(self) -> None:
        with self.assertRaises(MalformedModelOutput):
            parse_answer(
                support.ENTERPRISE_REFUND_QUESTION,
                support.DOCUMENTS,
                {
                    "answer": "This answer is not grounded.",
                    "evidence": [
                        {
                            "document_id": support.ENTERPRISE_REFUND_POLICY.document_id,
                            "quote": "No such sentence exists in the document.",
                        }
                    ],
                },
            )

    def test_index_rejects_duplicate_workflow_identifiers(self) -> None:
        with self.assertRaises(ValueError):
            build_reviewed_workflow_index(
                (support.REVIEWED_WORKFLOWS[0], support.REVIEWED_WORKFLOWS[0])
            )

    def test_match_reviewed_workflow_rejects_out_of_range_threshold(self) -> None:
        with self.assertRaises(ValueError):
            match_reviewed_workflow(
                (support.REFUND_INTENT,),
                support.WORKFLOW_INDEX,
                minimum_score=1.5,
            )


class ReviewedCacheConsistencyRegressionTests(unittest.TestCase):
    """A fresh alternative must pass its own impact and authorization gates."""

    @staticmethod
    def _answer(revision: str, text: str):
        document = KnowledgeDocument(
            source_id="support:kb",
            external_id="refund",
            title="Refund",
            body=text,
            revision=revision,
        )
        return parse_answer(
            "How long is the refund window?",
            (document,),
            {
                "answer": text,
                "evidence": [{"document_id": document.document_id, "quote": text}],
            },
        )

    def test_fresh_reviewed_cache_is_not_shadowed_by_a_stale_exact_match(self) -> None:
        stale = ReviewedWorkflow(
            identifier="refund-v1",
            name="Refund v1",
            match_vectors=((1.0, 0.0, 0.0, 0.0),),
            document_ids=("support:kb/refund", "support:kb/addendum"),
            cached_answer=self._answer("v1", "The refund window is 30 days."),
        )
        fresh = ReviewedWorkflow(
            identifier="refund-v2",
            name="Refund v2",
            match_vectors=((0.95, 0.05, 0.0, 0.0),),
            document_ids=("support:kb/refund",),
            cached_answer=self._answer("v2", "The refund window is 60 days."),
        )
        index = build_reviewed_workflow_index((stale, fresh))
        revisions = {"support:kb/refund": "v2"}
        policy = WorkflowPolicy()
        query = ((1.0, 0.0, 0.0, 0.0),)

        cache = match_cached_response(
            query, index, revisions, minimum_score=policy.cache_threshold
        )
        self.assertTrue(cache.reusable)
        self.assertEqual(cache.match.workflow.identifier, "refund-v2")

        decision = decide_reviewed_workflow(query, index, revisions, policy=policy)
        self.assertIs(decision.action, WorkflowAction.CACHED_RESPONSE)
        self.assertEqual(decision.match.workflow.identifier, "refund-v2")

        # This source belonged to the stale workflow, but is new to the fresh
        # alternative. Evaluate impact against the alternative's dependencies.
        for impact in ({}, {"support:kb/addendum": True}):
            blocked = decide_reviewed_workflow(
                query,
                index,
                revisions,
                policy=policy,
                relevant_document_scores={"support:kb/addendum": 1.0},
                impact_decisions=impact,
            )
            self.assertIs(blocked.action, WorkflowAction.SPECULATIVE_RETRIEVAL)
            self.assertIsNone(blocked.cached_answer)
        cleared = decide_reviewed_workflow(
            query,
            index,
            revisions,
            policy=policy,
            relevant_document_scores={"support:kb/addendum": 1.0},
            impact_decisions={"support:kb/addendum": False},
        )
        self.assertIs(cleared.action, WorkflowAction.CACHED_RESPONSE)
        denied = decide_reviewed_workflow(
            query, index, revisions, policy=policy, allowed_document_ids=set()
        )
        self.assertIs(denied.action, WorkflowAction.LLM)
        self.assertIsNone(denied.cached_answer)


if __name__ == "__main__":
    unittest.main()
