from __future__ import annotations

import asyncio
import unittest

from mari_components import KnowledgeDocument
from mari_components.agents import (
    AgentEvent,
    EventKind,
    evaluate_outcome,
    evaluate_tools,
)
from mari_components.errors import MalformedModelOutput
from mari_components.knowledge import impacted_artifacts, parse_answer
from mari_components.trajectories import (
    CacheDecisionReason,
    ReviewedWorkflow,
    WorkflowAction,
    WorkflowPolicy,
    build_reviewed_workflow_index,
    decide_reviewed_workflow,
    match_cached_response,
    match_reviewed_workflow,
    normalize_steps,
    parse_trajectory_analysis,
    start_speculative_retrieval,
)


def grounded_answer(text: str, revision: str):
    document = KnowledgeDocument(
        source_id="docs",
        external_id="refund",
        title="Refund policy",
        body=text,
        revision=revision,
    )
    return parse_answer(
        "What is the refund policy?",
        (document,),
        {
            "answer": text,
            "evidence": [{"document_id": document.document_id, "quote": text}],
        },
    )


class TrajectoryAgentTests(unittest.TestCase):
    def test_direct_framework_events_support_portable_evaluation(self):
        events = (
            AgentEvent(
                kind=EventKind.TOOL_CALL,
                name="search",
                arguments={"query": "retention"},
            ),
            AgentEvent(
                kind=EventKind.TOOL_RESULT,
                name="search",
                result={"document_id": "docs/1"},
            ),
            AgentEvent(kind=EventKind.ANSWER, result="Retention is 30 days [docs/1]."),
        )
        self.assertTrue(evaluate_tools(events, expected_tools=("search",)).passed)

    def test_failed_framework_tool_result_fails_evaluation(self):
        events = (
            AgentEvent(kind=EventKind.TOOL_CALL, name="search"),
            AgentEvent(
                kind=EventKind.TOOL_RESULT, name="search", result="timeout", ok=False
            ),
        )
        self.assertFalse(evaluate_tools(events, expected_tools=("search",)).passed)

    def test_trajectory_redacts_arguments_and_validates_model_labels(self):
        events = [
            {
                "name": "search",
                "args": {"query": "retention", "token": "secret"},
                "summary": "Found docs",
                "ok": True,
            },
            {
                "name": "tag_document",
                "args": {"id": 1},
                "summary": "Tagged",
                "ok": False,
            },
            {
                "name": "tag_document",
                "args": {"id": 1},
                "summary": "Tagged",
                "ok": True,
            },
        ]
        self.assertNotIn("token", normalize_steps(events)[0].arguments)
        analysis = parse_trajectory_analysis(
            events,
            {
                "workflow": "Searched, then tagged after a retry.",
                "activity": "Classified product knowledge.",
                "category": "Knowledge maintenance",
                "intent": "Organize retention knowledge",
                "rework": 1,
                "phases": [
                    {
                        "name": "Find",
                        "family": "discover",
                        "start": 0,
                        "end": 0,
                        "substate": "Completed",
                    },
                    {
                        "name": "Tag",
                        "family": "change",
                        "start": 1,
                        "end": 2,
                        "substate": "Recovered",
                    },
                ],
            },
        )
        self.assertEqual(analysis.category, "Knowledge maintenance")
        self.assertEqual(analysis.phases[1].failures, 1)
        self.assertEqual(analysis.rework, 1)

    def test_model_phase_spans_must_cover_observed_steps(self):
        with self.assertRaises(MalformedModelOutput):
            parse_trajectory_analysis(
                [{"name": "search", "ok": True}],
                {
                    "workflow": "Searched.",
                    "activity": "Search.",
                    "category": "Search",
                    "intent": "Find answer",
                    "rework": 0,
                    "phases": [],
                },
            )

    def test_product_neutral_outcome_evaluation(self):
        result = evaluate_outcome(
            paths=("/settings",),
            expected_paths=("/settings",),
            tool_results=(("test_connection", True),),
            expected_tools=("test_connection",),
        )
        self.assertTrue(result.passed)

    def test_reviewed_cache_skips_stale_higher_scoring_workflow(self):
        stale = ReviewedWorkflow(
            identifier="exact",
            name="Exact refunds",
            match_vectors=((1.0, 0.0, 0.0, 0.0),),
            document_ids=("docs/refund",),
            cached_answer=grounded_answer("Stale answer", "v1"),
        )
        fresh = ReviewedWorkflow(
            identifier="near",
            name="Nearby refunds",
            match_vectors=((0.95, 0.05, 0.0, 0.0),),
            document_ids=("docs/refund",),
            cached_answer=grounded_answer("Fresh answer", "v2"),
        )
        query = ((1.0, 0.0, 0.0, 0.0),)
        index = build_reviewed_workflow_index((stale, fresh))
        match = match_reviewed_workflow(query, index, minimum_score=0.9)
        self.assertEqual(match.workflow.identifier, "exact")
        cache = match_cached_response(
            query,
            index,
            {"docs/refund": "v2"},
            minimum_score=0.9,
        )
        self.assertEqual(cache.match.workflow.identifier, "near")
        impacts = impacted_artifacts(
            {
                "workflow:exact": stale.cached_answer.knowledge_dependencies,
                "workflow:near": fresh.cached_answer.knowledge_dependencies,
            },
            {"docs/refund": "v2"},
        )
        self.assertEqual(tuple(impacts), ("workflow:exact",))

    def test_cache_requires_extreme_match_and_accounts_for_new_documents(self):
        workflow = ReviewedWorkflow(
            identifier="refund",
            name="Refund",
            match_vectors=((1.0, 0.0, 0.0, 0.0),),
            document_ids=("docs/refund",),
            cached_answer=grounded_answer("Thirty days.", "v1"),
        )
        index = build_reviewed_workflow_index((workflow,))
        policy = WorkflowPolicy(
            speculation_threshold=0.7,
            cache_threshold=0.97,
            relevant_document_threshold=0.85,
        )
        query = ((1.0, 0.0, 0.0, 0.0),)
        cached = decide_reviewed_workflow(
            query, index, {"docs/refund": "v1"}, policy=policy
        )
        self.assertEqual(cached.action, WorkflowAction.CACHED_RESPONSE)
        unresolved = decide_reviewed_workflow(
            query,
            index,
            {"docs/refund": "v1"},
            relevant_document_scores={"docs/new": 0.99},
            policy=policy,
        )
        self.assertEqual(unresolved.action, WorkflowAction.SPECULATIVE_RETRIEVAL)
        cleared = decide_reviewed_workflow(
            query,
            index,
            {"docs/refund": "v1"},
            relevant_document_scores={"docs/new": 0.99},
            impact_decisions={"docs/new": False},
            policy=policy,
        )
        self.assertEqual(cleared.action, WorkflowAction.CACHED_RESPONSE)

    def test_cache_matching_excludes_workflows_with_unauthorized_dependencies(self):
        private = ReviewedWorkflow(
            identifier="private",
            name="Private mitigation",
            match_vectors=((1.0, 0.0, 0.0, 0.0),),
            document_ids=("docs/private",),
            cached_answer=parse_answer(
                "What should I do?",
                (
                    KnowledgeDocument(
                        source_id="docs",
                        external_id="private",
                        title="Private",
                        body="Use the private mitigation.",
                        revision="v1",
                    ),
                ),
                {
                    "answer": "Use the private mitigation.",
                    "evidence": [
                        {
                            "document_id": "docs/private",
                            "quote": "Use the private mitigation.",
                        }
                    ],
                },
            ),
        )
        public = ReviewedWorkflow(
            identifier="public",
            name="Public guidance",
            match_vectors=((0.95, 0.05, 0.0, 0.0),),
            document_ids=("docs/public",),
            cached_answer=parse_answer(
                "What should I do?",
                (
                    KnowledgeDocument(
                        source_id="docs",
                        external_id="public",
                        title="Public",
                        body="Use the public status page.",
                        revision="v1",
                    ),
                ),
                {
                    "answer": "Use the public status page.",
                    "evidence": [
                        {
                            "document_id": "docs/public",
                            "quote": "Use the public status page.",
                        }
                    ],
                },
            ),
        )
        decision = decide_reviewed_workflow(
            ((1.0, 0.0, 0.0, 0.0),),
            build_reviewed_workflow_index((private, public)),
            {"docs/private": "v1", "docs/public": "v1"},
            allowed_document_ids={"docs/public"},
            policy=WorkflowPolicy(speculation_threshold=0.7, cache_threshold=0.97),
        )
        self.assertEqual(decision.action, WorkflowAction.CACHED_RESPONSE)
        self.assertEqual(decision.match.workflow.identifier, "public")
        hidden = match_cached_response(
            ((1.0, 0.0, 0.0, 0.0),),
            build_reviewed_workflow_index((private,)),
            {"docs/private": "v1"},
            minimum_score=0.0,
            allowed_document_ids=set(),
        )
        self.assertEqual(hidden.reason, CacheDecisionReason.NO_CACHED_RESPONSE)


class SpeculativeRetrievalTests(unittest.IsolatedAsyncioTestCase):
    async def test_reviewed_read_starts_as_a_real_async_task(self):
        workflow = ReviewedWorkflow(
            identifier="refund",
            name="Refund",
            match_vectors=((1.0, 0.0),),
            document_ids=("docs/refund",),
        )
        decision = decide_reviewed_workflow(
            ((1.0, 0.0),),
            build_reviewed_workflow_index((workflow,)),
            {},
            policy=WorkflowPolicy(speculation_threshold=0.7, cache_threshold=0.97),
        )
        started = asyncio.Event()

        async def retrieve(document_ids):
            started.set()
            await asyncio.sleep(0)
            return document_ids

        task = start_speculative_retrieval(decision, retrieve)
        await started.wait()
        self.assertEqual(await task, ("docs/refund",))


if __name__ == "__main__":
    unittest.main()
