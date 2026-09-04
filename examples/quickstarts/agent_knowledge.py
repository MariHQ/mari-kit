"""Turn completed tool activity into a validated, reviewable memory plan."""

from mari_components.knowledge import (
    MemoryDecision,
    MemoryOperation,
    plan_memory_mutations,
)
from mari_components.trajectories import parse_trajectory_analysis


def run() -> dict[str, object]:
    events = (
        {"name": "search", "args": {"query": "refund policy"}, "ok": True},
        {"name": "read_document", "args": {"document_id": "refunds"}, "ok": True},
        {"name": "approve_answer", "args": {"answer_id": "answer-7"}, "ok": True},
    )
    analysis = parse_trajectory_analysis(
        events,
        {
            "workflow": "Find the current policy, inspect its source, and approve the answer.",
            "activity": "Answer a policy question",
            "category": "support",
            "intent": "resolve_refund_question",
            "rework": 0,
            "phases": [
                {
                    "name": "research",
                    "family": "discover",
                    "start": 0,
                    "end": 1,
                    "substate": "grounding",
                },
                {
                    "name": "review",
                    "family": "approve",
                    "start": 2,
                    "end": 2,
                    "substate": "complete",
                },
            ],
        },
    )
    candidates = {"procedure:refund-answer": analysis.grounded_workflow}
    plan = plan_memory_mutations(
        {},
        candidates,
        {
            "procedure:refund-answer": MemoryDecision(
                operation=MemoryOperation.ADD,
                reason="successful reviewed run",
            )
        },
    )
    return {
        "analysis": analysis,
        "proposal": plan.writes[0],
        "target_id": plan.writes[0].target_id,
    }


if __name__ == "__main__":
    print(run())
