#!/usr/bin/env python3
"""Exercise knowledge-from-experience primitives against a public fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mari_components.knowledge import (
    ExpertFeedback,
    KnowledgeUse,
    TrajectoryEvidence,
    build_knowledge_use_manifest,
    parse_feedback_diagnoses,
)
from mari_components.trajectories import mine_outcome_associations, normalize_steps
from mari_components.trajectories.process import TrajectoryRun


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugmem-fixture", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/results/experience-knowledge.json"),
    )
    args = parser.parse_args()
    fixture = json.loads(args.plugmem_fixture.read_text())
    sessions = fixture["sessions"]
    event_count = sum(len(session["events"]) for session in sessions)
    tool_events = [
        event
        for session in sessions
        for event in session["events"]
        if event["type"] == "post_tool"
    ]
    public_run = TrajectoryRun(
        trajectory_id="plugmem-smoke:session-1",
        steps=normalize_steps(
            {
                "name": event["toolName"],
                "ok": event.get("outcome") == "success",
                "event_id": event["callId"],
            }
            for event in tool_events
        ),
        outcome="success",
    )

    planted = tuple(
        TrajectoryRun(
            trajectory_id=f"{outcome}-{index}",
            steps=normalize_steps(
                {"name": tool, "ok": outcome == "success"}
                for tool in (
                    ("search", "answer")
                    if outcome == "success"
                    else ("search", "retry", "answer")
                )
            ),
            outcome=outcome,
        )
        for outcome in ("success", "failure")
        for index in range(2)
    )
    retry = next(
        item
        for item in mine_outcome_associations(planted)
        if item.pattern == ("retry",)
    )
    manifest = build_knowledge_use_manifest(
        public_run,
        [
            KnowledgeUse(
                artifact_id="project-conventions",
                revision="fixture",
                first_step=0,
                last_step=1,
                use="choose and verify the project HTTP client",
            )
        ],
    )
    feedback = ExpertFeedback(
        feedback_id="http-client-correction",
        correction="Use httpx, not requests.",
        evidence=TrajectoryEvidence(
            trajectory_id=public_run.trajectory_id, start=0, end=1
        ),
    )
    diagnoses = parse_feedback_diagnoses(
        [public_run],
        [manifest],
        [feedback],
        {
            "diagnoses": [
                {
                    "feedback_id": feedback.feedback_id,
                    "root_cause": "procedure_gap",
                    "could_resolve_from_loaded_knowledge": True,
                    "supporting_artifact_ids": ["project-conventions"],
                    "explanation": "The convention was available to the run.",
                }
            ]
        },
    )
    result = {
        "corpus": {
            "name": "PlugMem coding smoke fixture",
            "license": "Apache-2.0",
            "fixture": args.plugmem_fixture.name,
            "sessions": len(sessions),
            "events": event_count,
            "tool_results": len(tool_events),
            "explicit_failures": sum(step.ok is False for step in public_run.steps),
            "explicit_successes": sum(step.ok is True for step in public_run.steps),
        },
        "known_answer": {
            "retry_success_support": retry.success_support,
            "retry_failure_support": retry.failure_support,
            "retry_failure_risk_ratio": retry.failure_risk_ratio,
            "retry_interval": retry.risk_ratio_interval,
            "diagnoses_accepted": len(diagnoses),
            "loaded_artifact_citations": len(diagnoses[0].supporting_artifact_ids),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
