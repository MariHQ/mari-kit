from __future__ import annotations

import unittest

from mari_components.agents import EvalCase, OutcomeEvalCase, Tool, ToolEvalCase, evaluate_answer, evaluate_outcome, evaluate_tools, run_tool_loop
from mari_components.trajectories import (
    analyze_trajectory, distill_workflows, match_workflow, normalize_steps,
    rework_count, segment_phases,
)


class TrajectoryAgentTests(unittest.TestCase):
    def test_trajectory_redacts_segments_and_mines(self):
        events = [
            {"name": "search", "args": {"query": "retention", "token": "secret"}, "summary": "Found docs", "ok": True},
            {"name": "tag_document", "args": {"id": 1}, "summary": "Tagged", "ok": False},
            {"name": "tag_document", "args": {"id": 1}, "summary": "Tagged", "ok": True},
        ]
        steps = normalize_steps(events)
        self.assertNotIn("token", steps[0].arguments)
        self.assertGreaterEqual(len(segment_phases(steps)), 2)
        self.assertEqual(rework_count(steps), 1)
        values = iter([
            {"workflow": "Searched, then tagged after a retry."},
            {"activity": "Classified product knowledge."},
            {"category": "Knowledge maintenance"},
            {"intent": "Organize retention knowledge"},
        ])
        analysis = analyze_trajectory("organize this", events, generate_json=lambda _p, _v: next(values))
        self.assertEqual(analysis.category, "Knowledge maintenance")

    def test_agent_loop_and_outcome_evals(self):
        decisions = iter([
            {"action": "tool", "tool": "search", "arguments": {"query": "retention"}},
            {"action": "answer"},
        ])
        events = tuple(run_tool_loop(
            [{"role": "user", "content": "How long?"}],
            [Tool("search", "Search knowledge", lambda _args: {"doc": "doc:1"})],
            generate_json=lambda _p, _v: next(decisions),
            stream_answer=lambda _messages: ("Retention is ", "30 days [doc:1]."),
            authorize_write=lambda _tool, _args: False,
        ))
        answer = "".join(str(event.result) for event in events if event.kind == "answer_delta")
        self.assertTrue(evaluate_tools(ToolEvalCase("tools", ("search",)), events).passed)
        self.assertTrue(evaluate_answer(EvalCase("answer", ("30 days",), require_citations=True), answer, citation_count=1).passed)

    def test_grounded_loop_refuses_to_answer_before_observing_a_tool(self):
        decisions = iter([
            {"action": "answer"},
            {"action": "tool", "tool": "search", "arguments": {"query": "Mari"}},
            {"action": "answer"},
        ])
        events = tuple(run_tool_loop(
            [{"role": "user", "content": "What is Mari?"}],
            [Tool("search", "Search knowledge", lambda _args: {"title": "Mari README"})],
            generate_json=lambda _p, _v: next(decisions),
            stream_answer=lambda _messages: ("Mari is a product knowledge system [Mari README].",),
            authorize_write=lambda _tool, _args: False,
            minimum_tool_observations=1,
        ))
        self.assertEqual([event.kind for event in events], [
            "tool_call", "tool_result", "answer_delta", "answer_complete",
        ])

    def test_agent_retries_one_malformed_structured_decision(self):
        decisions = iter([
            None,
            {"action": "tool", "tool": "search", "arguments": {"query": "Mari"}},
            {"action": "answer"},
        ])
        events = tuple(run_tool_loop(
            [], [Tool("search", "Search", lambda _args: "Mari README")],
            generate_json=lambda _p, _v: next(decisions),
            stream_answer=lambda _messages: ("Grounded answer.",),
            authorize_write=lambda _tool, _args: False,
            minimum_tool_observations=1,
        ))
        self.assertEqual([event.kind for event in events], [
            "tool_call", "tool_result", "answer_delta", "answer_complete",
        ])

    def test_product_neutral_outcome_evaluation(self):
        result = evaluate_outcome(
            OutcomeEvalCase("setup", ("token",), ("/settings",), ("test_connection",)),
            "Paste the token, then test it.",
            paths=("/settings",), tool_results=(("test_connection", True),), completed=True,
        )
        self.assertTrue(result.passed)

    def test_write_tool_requires_explicit_authorization(self):
        decisions = iter([
            {"action": "tool", "tool": "approve", "arguments": {"id": "fact:1"}},
            {"action": "answer"},
        ])
        calls = []
        events = tuple(run_tool_loop(
            [],
            [Tool("approve", "Approve fact", lambda args: calls.append(args), writes=True)],
            generate_json=lambda _p, _v: next(decisions),
            stream_answer=lambda _messages: ("Approval was not authorized.",),
            authorize_write=lambda _tool, _args: False,
        ))
        self.assertEqual(calls, [])
        self.assertFalse([event for event in events if event.kind == "tool_result"][0].ok)

    def test_observer_receives_events_as_they_happen(self):
        observed = []
        decisions = iter([
            {"action": "tool", "tool": "search", "arguments": {"query": "release"}},
            {"action": "answer"},
        ])
        stream = run_tool_loop(
            [], [Tool("search", "Search", lambda _args: "runbook")],
            generate_json=lambda _prompt, _version: next(decisions),
            stream_answer=lambda _messages: ("Use ", "main."),
            authorize_write=lambda _tool, _args: False,
            observe=observed.append,
        )
        self.assertEqual(observed, [])
        first = next(stream)
        self.assertEqual(first.kind, "tool_call")
        self.assertEqual(observed, [first])
        events = (first, *tuple(stream))
        self.assertEqual(tuple(observed), events)
        self.assertEqual([event.kind for event in observed], [
            "tool_call", "tool_result", "answer_delta", "answer_delta", "answer_complete",
        ])

    def test_partial_answer_is_yielded_before_stream_failure(self):
        def failing_answer(_messages):
            yield "Partial answer"
            raise ConnectionError("provider disconnected")

        stream = run_tool_loop(
            [], [],
            generate_json=lambda _prompt, _version: {"action": "answer"},
            stream_answer=failing_answer,
            authorize_write=lambda _tool, _args: False,
        )
        self.assertEqual(next(stream).result, "Partial answer")
        with self.assertRaises(ConnectionError):
            next(stream)

    def test_distillation_keeps_only_shape_and_matches_without_a_model(self):
        values = iter([
            {"workflow": "Searched release knowledge."},
            {"activity": "Answered release questions."},
            {"category": "Knowledge consumption"},
            {"intent": "Understand release process"},
        ] * 2)
        analyses = tuple(analyze_trajectory(
            "release", [{
                "name": "search", "args": {"query": secret},
                "summary": "found runbook", "ok": True,
            }], generate_json=lambda _prompt, _version: next(values),
        ) for secret in ("first private query", "second private query"))
        workflows = distill_workflows(analyses)
        self.assertEqual(len(workflows), 1)
        self.assertEqual(workflows[0].tool_sequence, ("search",))
        self.assertFalse(hasattr(workflows[0], "arguments"))
        self.assertIsNotNone(match_workflow("understand release", workflows, minimum_score=.05))


if __name__ == "__main__":
    unittest.main()
