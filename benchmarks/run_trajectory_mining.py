#!/usr/bin/env python3
"""Evaluate trajectory algorithms and a checked-out public trace corpus."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from pathlib import Path

from mari_components.errors import MalformedModelOutput
from mari_components.trajectories import (
    IntentReview,
    TrajectoryInvariantKind,
    TrajectoryMatchMode,
    TrajectoryRun,
    aggregate_intents,
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


def _steps(*tools: str):
    return normalize_steps(
        {"name": tool, "args": {"scope": "docs"}, "ok": True} for tool in tools
    )


def _public_runs(corpus: Path) -> tuple[TrajectoryRun, ...]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for path in sorted(corpus.glob("*.jsonl")):
        for line in path.read_text().splitlines():
            if not line.startswith("{"):
                continue
            row = json.loads(line)
            grouped[f"{path.stem}:{row['session']}"].append(row)
    runs = []
    for trajectory_id, rows in sorted(grouped.items()):
        rows.sort(key=lambda row: row["seq"])
        events = [
            {
                "name": row["action"],
                "ok": True
                if row.get("outcome") == "ok"
                else False
                if row.get("outcome") == "error"
                else None,
                "event_id": f"{trajectory_id}:{row['seq']}",
            }
            for row in rows
        ]
        runs.append(
            TrajectoryRun(
                trajectory_id=trajectory_id,
                steps=normalize_steps(events),
                outcome="unknown",
            )
        )
    return tuple(runs)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plumbline-corpus", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path("benchmarks/results/trajectory-mining.json")
    )
    args = parser.parse_args()

    public_runs = _public_runs(args.plumbline_corpus)
    public_process = mine_trajectory_process(public_runs)

    successful = tuple(
        TrajectoryRun(
            trajectory_id=f"known-{index}",
            steps=_steps("search", "read", "answer"),
            outcome="success",
        )
        for index in range(3)
    )
    invariants = mine_trajectory_invariants(
        successful, available_tools=("search", "read", "answer", "delete")
    )
    expected = {
        *(f"always_calls:{tool}" for tool in ("search", "read", "answer")),
        *(f"always_succeeds:{tool}" for tool in ("search", "read", "answer")),
        *(f"max_calls:{tool}" for tool in ("search", "read", "answer")),
        "never_calls:delete",
        "precedes:search:read",
        "precedes:search:answer",
        "precedes:read:answer",
    }
    observed = {
        f"{item.kind.value}:{item.tool}"
        + (
            f":{item.other_tool}"
            if item.kind is TrajectoryInvariantKind.PRECEDES
            else ""
        )
        for item in invariants
    }
    regression = TrajectoryRun(
        trajectory_id="regression",
        steps=_steps("read", "search", "delete", "answer"),
        outcome="success",
    )
    violations = tuple(
        value
        for item in invariants
        if (value := check_trajectory_invariant(item, regression)) is not None
    )

    reference = _steps("search", "read", "answer")
    match_cases = (
        compare_trajectories(reference, reference).matched,
        compare_trajectories(
            _steps("search", "answer"),
            reference,
            mode=TrajectoryMatchMode.SUBSEQUENCE,
        ).matched,
        compare_trajectories(
            _steps("answer", "read", "search"),
            reference,
            mode=TrajectoryMatchMode.UNORDERED,
        ).matched,
        not compare_trajectories(_steps("read", "search"), reference).matched,
    )

    vectors = {
        f"cluster-{cluster}-{point}": tuple(
            1.0 if dimension == cluster else point * 0.01 for dimension in range(4)
        )
        for cluster in range(4)
        for point in range(3)
    }
    sample = select_diverse_trajectories(vectors, limit=4)
    cluster_coverage = len(
        {item.trajectory_id.split("-")[1] for item in sample.selected}
    )

    openai = normalize_openai_trajectory(
        (
            {
                "type": "function_call",
                "call_id": "1",
                "name": "search",
                "arguments": "{}",
                "status": "completed",
            },
        )
    )
    anthropic = normalize_anthropic_trajectory(
        ({"content": [{"type": "tool_use", "id": "1", "name": "search", "input": {}}]},)
    )
    otel = normalize_otel_trajectory(
        (
            {
                "span_id": "1",
                "status": {"code": "OK"},
                "attributes": {"gen_ai.tool.name": "search"},
            },
        )
    )
    adapter_cases = (
        len(openai.steps) == 1
        and openai.steps[0].tool == "search"
        and openai.steps[0].ok is None,
        len(anthropic.steps) == 1
        and anthropic.steps[0].tool == "search"
        and anthropic.steps[0].ok is None,
        len(otel.steps) == 1
        and otel.steps[0].tool == "search"
        and otel.steps[0].ok is True,
    )

    intent_runs = (
        TrajectoryRun(
            trajectory_id="intent-a",
            steps=_steps("search", "answer"),
            outcome="success",
        ),
        TrajectoryRun(
            trajectory_id="intent-b",
            steps=_steps("search", "answer"),
            outcome="failure",
        ),
    )
    candidates = parse_intent_candidates(
        intent_runs,
        {
            "intents": [
                {
                    "intent": "Answer retention questions",
                    "kind": "inferred",
                    "evidence": [{"trajectory_id": "intent-a", "start": 0, "end": 1}],
                },
                {
                    "intent": "answer—retention questions",
                    "kind": "hindsight",
                    "evidence": [{"trajectory_id": "intent-b", "start": 0, "end": 1}],
                },
            ]
        },
    )
    intent_groups = aggregate_intents(candidates)
    intent_evidence_rejections = 0
    try:
        parse_intent_candidates(
            intent_runs,
            {
                "intents": [
                    {
                        "intent": "invalid range",
                        "evidence": [
                            {"trajectory_id": "intent-a", "start": 0, "end": 99}
                        ],
                    }
                ]
            },
        )
    except MalformedModelOutput:
        intent_evidence_rejections = 1
    review_summaries = summarize_intent_reviews(
        candidates,
        (
            IntentReview(
                candidate_id=candidates[1].candidate_id,
                reviewer_id="reviewer-a",
                valid=True,
            ),
            IntentReview(
                candidate_id=candidates[1].candidate_id,
                reviewer_id="reviewer-b",
                valid=False,
            ),
            IntentReview(
                candidate_id=candidates[1].candidate_id,
                reviewer_id="reviewer-b",
                valid=True,
            ),
        ),
    )
    review_summary = next(
        item
        for item in review_summaries
        if item.candidate_id == candidates[1].candidate_id
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
    rubric_score = score_trajectory_rubric(
        intent_runs[0],
        rubric,
        parse_rubric_assessments(
            intent_runs[0],
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
        ),
    )
    report = {
        "schema_version": 1,
        "mari_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "reference": {
            "repository": "askalf/plumbline",
            "commit": "1cea591e6da5",
            "license": "MIT",
            "files": len(tuple(args.plumbline_corpus.glob("*.jsonl"))),
            "trajectories": len(public_runs),
            "events": public_process.event_count,
            "activities": len(public_process.activities),
            "variants": len(public_process.variants),
            "rework_rate": round(public_process.rework_rate, 6),
        },
        "known_answer": {
            "invariant_precision": len(observed & expected) / len(observed),
            "invariant_recall": len(observed & expected) / len(expected),
            "invariants": len(invariants),
            "regression_violations": len(violations),
            "trajectory_match_cases": sum(match_cases),
            "trajectory_match_total": len(match_cases),
            "diverse_sample_cluster_coverage": cluster_coverage,
            "diverse_sample_clusters": 4,
            "adapter_cases": sum(adapter_cases),
            "adapter_total": len(adapter_cases),
            "intent_groups": len(intent_groups),
            "intent_group_support": intent_groups[0].support,
            "intent_evidence_rejections": intent_evidence_rejections,
            "intent_review_valid": review_summary.valid_reviews,
            "intent_review_invalid": review_summary.invalid_reviews,
            "intent_review_duplicates": len(review_summary.duplicate_reviewer_ids),
            "rubric_overall": round(rubric_score.overall, 6),
            "rubric_missing_dimensions": len(rubric_score.missing_dimensions),
            "rubric_required_failures": len(rubric_score.required_failures),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
