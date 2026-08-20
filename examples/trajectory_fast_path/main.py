"""Observe agent runs → mine trajectories → distill → execute a fast path."""

from __future__ import annotations

import json
import os
from typing import Mapping

from mari_components import KnowledgeDocument
from mari_components.agents import AgentEvent, Tool, run_tool_loop
from mari_components.knowledge import answer_question
from mari_components.trajectories import (
    analyze_trajectory, distill_workflows, match_workflow,
)

from examples.support import json_generator, required


DOCUMENT = KnowledgeDocument(
    "runbook", "Release runbook", "Release Mari by deploying the tested main branch.",
)


def _telemetry(events: list[AgentEvent]):
    return ({
        "name": event.name or event.kind,
        "args": dict(event.arguments),
        "summary": str(event.result or event.kind),
        "ok": event.ok,
    } for event in events if event.kind != "tool_call")


def _analysis_model(_prompt: str, version: str) -> object:
    if version != "trajectory-mining-v1":
        raise AssertionError(version)
    # analyze_trajectory calls the same version for four progressively smaller
    # contracts; the requested JSON key remains visible in the prompt.
    if '"workflow"' in _prompt:
        return {"workflow": "Searched approved knowledge and returned a cited release answer."}
    if '"activity"' in _prompt:
        return {"activity": "Answered a release question from product knowledge."}
    if '"category"' in _prompt:
        return {"category": "Knowledge consumption"}
    return {"intent": "Understand release process"}


def _answer_model(_prompt: str, version: str) -> object:
    if version != "grounded-answer-v2":
        raise AssertionError(version)
    return {
        "answer": "Release Mari by deploying the tested main branch.",
        "evidence": [{
            "document_id": "runbook",
            "quote": "Release Mari by deploying the tested main branch.",
        }],
    }


def run(environment: Mapping[str, str] | None = None) -> dict[str, object]:
    env = os.environ if environment is None else environment
    # The example supports a real compatible model, but deterministic CI uses
    # an explicitly selected fixture. There is no model fallback.
    trajectory_model = json_generator(env, _analysis_model)
    answer_model = json_generator(env, _answer_model)
    minimum_score = float(required(env, "WORKFLOW_MATCH_MINIMUM_SCORE"))
    observed_runs: list[list[AgentEvent]] = []
    analyses = []
    online_planner_calls = 0

    for question in ("How do I release Mari?", "Explain the Mari release process"):
        events: list[AgentEvent] = []
        choices = iter([
            {"action": "tool", "tool": "search", "arguments": {"query": question}},
            {"action": "answer"},
        ])

        def planner(_prompt: str, _version: str) -> object:
            nonlocal online_planner_calls
            online_planner_calls += 1
            return next(choices)

        tuple(run_tool_loop(
            [{"role": "user", "content": question}],
            [Tool("search", "Search approved knowledge", lambda _args: DOCUMENT.body)],
            generate_json=planner,
            stream_answer=lambda _messages: (
                "Release Mari by deploying the tested main branch ", "[runbook].",
            ),
            authorize_write=lambda _tool, _arguments: False,
            observe=events.append,
        ))
        observed_runs.append(events)
        analyses.append(analyze_trajectory(
            question, _telemetry(events), generate_json=trajectory_model,
            taxonomy=("Knowledge consumption",),
        ))

    workflows = distill_workflows(analyses, minimum_occurrences=2)
    match = match_workflow(
        "How should I release Mari?", workflows, minimum_score=minimum_score,
    )
    if match is None:
        raise RuntimeError("no distilled workflow matched the request")

    # The host explicitly approves/binds this known workflow. No arguments or
    # side effects are replayed from telemetry. The fast path performs search
    # directly and needs only the final grounded-answer model invocation.
    fast_path_model_calls = 0
    def counted_answer(prompt: str, version: str) -> object:
        nonlocal fast_path_model_calls
        fast_path_model_calls += 1
        return answer_model(prompt, version)
    answer = answer_question(
        "How should I release Mari?", (DOCUMENT,), generate_json=counted_answer,
    )
    return {
        "observed_runs": len(observed_runs),
        "observed_events": sum(len(events) for events in observed_runs),
        "distilled_workflows": len(workflows),
        "workflow_tools": match.workflow.tool_sequence,
        "workflow_occurrences": match.workflow.occurrences,
        "online_planner_calls_per_request": online_planner_calls / len(observed_runs),
        "fast_path_model_calls": fast_path_model_calls,
        "faster": fast_path_model_calls < online_planner_calls / len(observed_runs),
        "answer": answer.answer,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
