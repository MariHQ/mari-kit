"""Show selective answer and workflow invalidation after a runbook edit."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping

from examples.support import selected_mode
from mari_components import KnowledgeDocument
from mari_components.knowledge import (
    KnowledgeDependency,
    impacted_artifacts,
    parse_answer,
    section_revisions,
)
from mari_components.trajectories import (
    ReviewedWorkflow,
    WorkflowAction,
    WorkflowPolicy,
    build_reviewed_workflow_index,
    decide_reviewed_workflow,
)

RUNBOOK_V1 = KnowledgeDocument(
    source_id="github:acme/operations",
    external_id="checkout-runbook.md",
    title="Checkout incident runbook",
    body="""# Checkout incident

## Detection
Page on sustained checkout error rates above five percent.

## Mitigation
Shift checkout traffic to the warm region and verify error rates recover.

## Escalation
Page the payments incident commander if errors remain elevated for ten minutes.
""",
    revision="runbook-v11",
)
RUNBOOK_V2 = KnowledgeDocument(
    source_id=RUNBOOK_V1.source_id,
    external_id=RUNBOOK_V1.external_id,
    title=RUNBOOK_V1.title,
    body="""# Checkout incident

## Detection
Page on sustained checkout error rates above five percent.

## Mitigation
Drain the degraded region before shifting checkout traffic to the warm region.

## Escalation
Page the payments incident commander if errors remain elevated for ten minutes.
""",
    revision="runbook-v12",
)
INCIDENT_THREAD = KnowledgeDocument(
    source_id="slack:acme",
    external_id="thread:checkout-1042",
    title="Checkout incident 1042",
    body="The on-call engineer confirmed that checkout errors are still elevated.",
    revision="1710000001.000200",
)


def _answer(
    question: str,
    answer: str,
    quote: str,
    *,
    include_incident_state: bool = False,
):
    evidence = [{"document_id": RUNBOOK_V1.document_id, "quote": quote}]
    if include_incident_state:
        evidence.append(
            {
                "document_id": INCIDENT_THREAD.document_id,
                "quote": INCIDENT_THREAD.body,
            }
        )
    return parse_answer(
        question,
        (RUNBOOK_V1, INCIDENT_THREAD),
        {
            "answer": answer,
            "evidence": evidence,
        },
    )


def run(environment: Mapping[str, str] | None = None) -> dict[str, object]:
    env = os.environ if environment is None else environment
    mode = selected_mode(env)
    mitigation = _answer(
        "How do we mitigate checkout errors?",
        "Errors remain elevated. Shift checkout traffic to the warm region and "
        "verify recovery.",
        "Shift checkout traffic to the warm region and verify error rates recover.",
        include_incident_state=True,
    )
    escalation = _answer(
        "When do we escalate checkout errors?",
        "Page the payments incident commander after ten elevated minutes.",
        "Page the payments incident commander if errors remain elevated for ten minutes.",
    )
    workflows = (
        ReviewedWorkflow(
            identifier="checkout-mitigation",
            name="Mitigate elevated checkout errors",
            match_vectors=((1.0, 0.0, 0.0, 0.0),),
            document_ids=tuple(
                row.document_id for row in mitigation.knowledge_dependencies
            ),
            cached_answer=mitigation,
        ),
        ReviewedWorkflow(
            identifier="checkout-escalation",
            name="Escalate sustained checkout errors",
            match_vectors=((0.0, 1.0, 0.0, 0.0),),
            document_ids=tuple(
                row.document_id for row in escalation.knowledge_dependencies
            ),
            cached_answer=escalation,
        ),
    )
    index = build_reviewed_workflow_index(workflows)
    current_revisions = {
        RUNBOOK_V2.document_id: RUNBOOK_V2.revision,
        INCIDENT_THREAD.document_id: INCIDENT_THREAD.revision,
    }
    current_sections = section_revisions((RUNBOOK_V2, INCIDENT_THREAD))
    artifacts = {
        "answer:checkout-mitigation": mitigation.knowledge_dependencies,
        "answer:checkout-escalation": escalation.knowledge_dependencies,
        "workflow:checkout-mitigation": mitigation.knowledge_dependencies,
        "workflow:checkout-escalation": escalation.knowledge_dependencies,
        "digest:whole-checkout-runbook": (
            KnowledgeDependency(
                document_id=RUNBOOK_V1.document_id,
                revision=RUNBOOK_V1.revision,
            ),
        ),
    }
    impacts = impacted_artifacts(
        artifacts,
        current_revisions,
        current_section_revisions=current_sections,
    )
    policy = WorkflowPolicy(speculation_threshold=0.70, cache_threshold=0.97)
    mitigation_decision = decide_reviewed_workflow(
        ((1.0, 0.0, 0.0, 0.0),),
        index,
        current_revisions,
        current_section_revisions=current_sections,
        policy=policy,
    )
    escalation_decision = decide_reviewed_workflow(
        ((0.0, 1.0, 0.0, 0.0),),
        index,
        current_revisions,
        current_section_revisions=current_sections,
        policy=policy,
    )
    changed_dependencies = tuple(
        change.dependency_id for report in impacts.values() for change in report.changes
    )
    return {
        "mode": mode,
        "old_runbook_revision": RUNBOOK_V1.revision,
        "new_runbook_revision": RUNBOOK_V2.revision,
        "mitigation_section": mitigation.evidence[0].section_id,
        "escalation_section": escalation.evidence[0].section_id,
        "mitigation_sources": tuple(
            row.document_id for row in mitigation.knowledge_dependencies
        ),
        "impacted_artifacts": tuple(impacts),
        "changed_dependencies": tuple(sorted(set(changed_dependencies))),
        "mitigation_action_after_change": mitigation_decision.action.value,
        "escalation_action_after_change": escalation_decision.action.value,
        "unchanged_escalation_cache_preserved": (
            escalation_decision.action is WorkflowAction.CACHED_RESPONSE
        ),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
