from __future__ import annotations

import pytest

from mari_components.errors import MalformedModelOutput
from mari_components.trajectories import (
    IntentKind,
    IntentReview,
    TrajectoryInvariantKind,
    TrajectoryMatchMode,
    TrajectoryRun,
    aggregate_intents,
    canonicalize_activity,
    check_trajectory_invariant,
    compare_trajectories,
    mine_trajectory_invariants,
    mine_trajectory_process,
    normalize_anthropic_trajectory,
    normalize_openai_trajectory,
    normalize_otel_trajectory,
    normalize_steps,
    parse_intent_candidates,
    parse_rubric_assessments,
    parse_trajectory_rubric,
    score_trajectory_rubric,
    select_diverse_trajectories,
    summarize_intent_reviews,
)


def steps(*tools: str, parents: tuple[str, ...] = ()):
    return normalize_steps(
        [
            {
                "name": tool,
                "args": {"scope": "docs"},
                "ok": True,
                "event_id": f"e{index}",
                "parent_id": parents[index] if parents else "",
                "started_at": float(index),
                "ended_at": float(index + 1),
                "input_tokens": 10,
                "output_tokens": 2,
                "cost": 0.01,
            }
            for index, tool in enumerate(tools)
        ]
    )


def test_process_mining_canonicalizes_labels_and_separates_parallelism_from_rework():
    assert canonicalize_activity("search(query='x')-retry-2") == "search"
    run = TrajectoryRun(
        trajectory_id="t1",
        steps=steps(
            "search_4471", "read_file_1", "search_4472", parents=("p", "p", "")
        ),
        outcome="success",
    )
    process = mine_trajectory_process((run,))
    assert process.event_count == 3
    assert process.parallel_events == 2
    assert process.rework_events == 1
    assert process.total_tokens == 36
    assert process.total_cost == pytest.approx(0.03)
    transition = next(
        item
        for item in process.transitions
        if item.source == "search" and item.target == "read_file"
    )
    assert transition.parallel == 1


def test_common_trace_adapters_preserve_explicit_and_unknown_outcomes():
    openai = normalize_openai_trajectory(
        (
            {
                "role": "assistant",
                "id": "m1",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "function": {
                            "name": "search",
                            "arguments": '{"query":"refunds","token":"secret"}',
                        },
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call-1", "content": "found"},
        )
    )
    assert openai.steps[0].ok is None
    assert "token" not in openai.steps[0].arguments

    responses = normalize_openai_trajectory(
        (
            {
                "type": "function_call",
                "call_id": "call-2",
                "name": "search",
                "arguments": '{"query":"retention"}',
                "status": "completed",
            },
        )
    )
    # A streamed function call being complete does not prove the tool succeeded.
    assert responses.steps[0].ok is None

    anthropic = normalize_anthropic_trajectory(
        (
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "fetch", "input": {}}
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "t1", "is_error": True}
                ],
            },
        )
    )
    assert anthropic.steps[0].ok is False

    otel = normalize_otel_trajectory(
        (
            {
                "span_id": "s2",
                "start_time_unix_nano": 2_000_000_000,
                "status": {"code": "ERROR"},
                "attributes": {"gen_ai.tool.name": "write"},
            },
            {
                "span_id": "s1",
                "start_time_unix_nano": 1_000_000_000,
                "status": {"code": "OK"},
                "attributes": {"gen_ai.tool.name": "read"},
            },
        )
    )
    assert [step.tool for step in otel.steps] == ["read", "write"]
    assert [step.ok for step in otel.steps] == [True, False]

    otlp_json = normalize_otel_trajectory(
        (
            {
                "spanId": "s3",
                "startTimeUnixNano": "1000000000",
                "endTimeUnixNano": "2250000000",
                "status": {"code": "STATUS_CODE_OK"},
                "attributes": [
                    {
                        "key": "gen_ai.tool.name",
                        "value": {"stringValue": "search"},
                    },
                    {
                        "key": "gen_ai.usage.input_tokens",
                        "value": {"intValue": "12"},
                    },
                ],
            },
        )
    )
    assert otlp_json.steps[0].tool == "search"
    assert otlp_json.steps[0].ok is True
    assert otlp_json.steps[0].input_tokens == 12
    assert otlp_json.steps[0].duration == pytest.approx(1.25)


def test_trajectory_matching_exposes_alignment_and_distance():
    reference = steps("search", "read", "answer")
    observed = steps("search", "answer")
    subset = compare_trajectories(
        observed, reference, mode=TrajectoryMatchMode.SUBSEQUENCE
    )
    strict = compare_trajectories(observed, reference)
    assert subset.matched
    assert subset.missing_reference_indices == (1,)
    assert strict.matched is False
    assert strict.edit_distance == 1
    assert strict.normalized_similarity == pytest.approx(2 / 3)


def test_intent_candidates_are_range_grounded_aggregated_and_independently_reviewed():
    runs = (
        TrajectoryRun(
            trajectory_id="a", steps=steps("search", "answer"), outcome="success"
        ),
        TrajectoryRun(
            trajectory_id="b", steps=steps("search", "answer"), outcome="failure"
        ),
    )
    candidates = parse_intent_candidates(
        runs,
        {
            "intents": [
                {
                    "intent": "Answer retention questions",
                    "kind": "inferred",
                    "evidence": [{"trajectory_id": "a", "start": 0, "end": 1}],
                },
                {
                    "intent": "answer—retention questions",
                    "kind": "hindsight",
                    "actual_outcome": "Found and summarized the policy.",
                    "limitations": ["Did not update the source."],
                    "evidence": [{"trajectory_id": "b", "start": 0, "end": 1}],
                },
            ]
        },
    )
    assert candidates[1].kind is IntentKind.HINDSIGHT
    aggregate = aggregate_intents(candidates)[0]
    assert aggregate.support == 2
    reviews = summarize_intent_reviews(
        candidates,
        (
            IntentReview(
                candidate_id=candidates[1].candidate_id, reviewer_id="r1", valid=True
            ),
            IntentReview(
                candidate_id=candidates[1].candidate_id, reviewer_id="r2", valid=False
            ),
            IntentReview(
                candidate_id=candidates[1].candidate_id, reviewer_id="r2", valid=True
            ),
        ),
    )
    hindsight = next(
        item for item in reviews if item.candidate_id == candidates[1].candidate_id
    )
    assert (hindsight.valid_reviews, hindsight.invalid_reviews) == (1, 1)
    assert hindsight.duplicate_reviewer_ids == ("r2",)
    with pytest.raises(MalformedModelOutput, match="outside"):
        parse_intent_candidates(
            runs,
            {
                "intents": [
                    {
                        "intent": "bad range",
                        "evidence": [{"trajectory_id": "a", "start": 0, "end": 9}],
                    }
                ]
            },
        )


def test_invariants_use_only_successful_runs_and_detect_regressions():
    runs = (
        TrajectoryRun(
            trajectory_id="a", steps=steps("search", "read"), outcome="success"
        ),
        TrajectoryRun(
            trajectory_id="b", steps=steps("search", "read"), outcome="success"
        ),
        TrajectoryRun(trajectory_id="failed", steps=steps("delete"), outcome="failure"),
    )
    invariants = mine_trajectory_invariants(
        runs,
        available_tools=("search", "read", "delete"),
        argument_names=("scope",),
    )
    assert all("failed" not in item.supporting_trajectory_ids for item in invariants)
    assert any(
        item.kind is TrajectoryInvariantKind.NEVER_CALLS and item.tool == "delete"
        for item in invariants
    )
    ordering = next(
        item
        for item in invariants
        if item.kind is TrajectoryInvariantKind.PRECEDES
        and item.tool == "search"
        and item.other_tool == "read"
    )
    regression = TrajectoryRun(
        trajectory_id="regression", steps=steps("read", "search"), outcome="success"
    )
    violation = check_trajectory_invariant(ordering, regression)
    assert violation is not None
    assert violation.reason == "tool_order_changed"


def test_diverse_sampling_uses_original_embedding_space_and_reports_exclusions():
    result = select_diverse_trajectories(
        {"a": (1.0, 0.0), "b": (0.99, 0.01), "c": (0.0, 1.0)},
        limit=2,
    )
    assert [item.trajectory_id for item in result.selected] == ["a", "c"]
    assert result.selected[1].minimum_distance == pytest.approx(1.0)
    assert result.excluded_ids == ("b",)


def test_task_adaptive_rubric_keeps_missing_required_dimensions_visible():
    run = TrajectoryRun(
        trajectory_id="a", steps=steps("search", "answer"), outcome="success"
    )
    rubric = parse_trajectory_rubric(
        "answer a policy question",
        {
            "dimensions": [
                {
                    "id": "grounding",
                    "description": "Uses retrieved evidence",
                    "weight": 2,
                    "required": True,
                },
                {
                    "id": "efficiency",
                    "description": "Avoids unnecessary calls",
                    "weight": 1,
                },
            ]
        },
    )
    assessments = parse_rubric_assessments(
        run,
        rubric,
        {
            "assessments": [
                {
                    "dimension_id": "efficiency",
                    "score": 0.8,
                    "confidence": 0.75,
                    "evidence_steps": [0, 1],
                }
            ]
        },
    )
    score = score_trajectory_rubric(run, rubric, assessments)
    assert score.overall == pytest.approx(0.8)
    assert score.missing_dimensions == ("grounding",)
    assert score.required_failures == ("grounding",)
