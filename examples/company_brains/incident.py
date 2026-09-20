"""Incident-response company brain with selective source invalidation.

The brain keeps grounded answers and a digest, each recording the exact
document and Markdown section revisions it consumed. Given the current source
snapshot it reports which derived guidance must be recomputed, which source was
removed, and which guidance stays reusable because its own section is
unchanged. No credentials, network, storage, or model calls are required.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping

from mari_kit import KnowledgeDocument
from mari_kit.knowledge import (
    FreshnessReport,
    GroundedAnswer,
    KnowledgeDependency,
    document_sections,
    impacted_artifacts,
    parse_answer,
    section_revisions,
)

RUNBOOK_V1 = KnowledgeDocument(
    source_id="github:acme/operations",
    external_id="incident-runbook.md",
    title="Checkout incident runbook",
    body="""# Checkout incident runbook

## Detection
Page the on-call engineer when checkout error rates stay above five percent for five minutes.

## Mitigation
Shift checkout traffic to the warm region and verify error rates recover.

## Escalation
Page the payments incident commander if errors remain elevated after ten minutes.
""",
    revision="runbook-v11",
)

RUNBOOK_V2 = KnowledgeDocument(
    source_id=RUNBOOK_V1.source_id,
    external_id=RUNBOOK_V1.external_id,
    title=RUNBOOK_V1.title,
    body="""# Checkout incident runbook

## Detection
Page the on-call engineer when checkout error rates stay above five percent for five minutes.

## Mitigation
Drain the degraded checkout region before shifting traffic to the warm region.

## Escalation
Page the payments incident commander if errors remain elevated after ten minutes.
""",
    revision="runbook-v12",
)

INCIDENT_THREAD_V1 = KnowledgeDocument(
    source_id="slack:acme",
    external_id="thread:checkout-1042",
    title="Checkout incident 1042",
    body="The on-call engineer confirmed that checkout errors are still elevated.",
    revision="1710000001.000200",
)

INCIDENT_THREAD_V2 = KnowledgeDocument(
    source_id=INCIDENT_THREAD_V1.source_id,
    external_id=INCIDENT_THREAD_V1.external_id,
    title=INCIDENT_THREAD_V1.title,
    body=(
        "The on-call engineer confirmed that checkout errors are still elevated. "
        "Traffic is being drained from the degraded region."
    ),
    revision="1710000002.000200",
)

CUSTOMER_COMMS = KnowledgeDocument(
    source_id="github:acme/operations",
    external_id="customer-comms.md",
    title="Customer communications policy",
    body="""# Customer communications policy

## Status updates
Send a customer-visible status update within fifteen minutes of confirmed impact.
""",
    revision="comms-v7",
)


def grounded_answer(
    question: str,
    documents: Iterable[KnowledgeDocument],
    answer: str,
    evidence: Iterable[Mapping[str, str]],
) -> GroundedAnswer:
    """Validate one answer against exact source evidence.

    This delegates entirely to ``parse_answer``: unknown documents, quotes that
    are absent from the supplied revision, and grounded answers without evidence
    all raise instead of being silently repaired.
    """

    return parse_answer(
        question,
        documents,
        {"answer": answer, "evidence": list(evidence)},
    )


def build_answers() -> dict[str, GroundedAnswer]:
    """Return the reviewed answers the brain is allowed to reuse."""

    runbook_and_thread = (RUNBOOK_V1, INCIDENT_THREAD_V1)
    return {
        "answer:checkout-detection": grounded_answer(
            "How do we detect checkout incidents?",
            (RUNBOOK_V1,),
            "Page on-call once checkout errors stay above five percent for five minutes.",
            [
                {
                    "document_id": RUNBOOK_V1.document_id,
                    "quote": (
                        "Page the on-call engineer when checkout error rates stay "
                        "above five percent for five minutes."
                    ),
                }
            ],
        ),
        "answer:checkout-mitigation": grounded_answer(
            "How do we mitigate checkout errors?",
            runbook_and_thread,
            "Errors remain elevated: shift checkout traffic to the warm region and "
            "verify recovery.",
            [
                {
                    "document_id": RUNBOOK_V1.document_id,
                    "quote": (
                        "Shift checkout traffic to the warm region and verify error "
                        "rates recover."
                    ),
                },
                {
                    "document_id": INCIDENT_THREAD_V1.document_id,
                    "quote": INCIDENT_THREAD_V1.body,
                },
            ],
        ),
        "answer:checkout-escalation": grounded_answer(
            "When do we escalate checkout errors?",
            (RUNBOOK_V1,),
            "Page the payments incident commander after ten elevated minutes.",
            [
                {
                    "document_id": RUNBOOK_V1.document_id,
                    "quote": (
                        "Page the payments incident commander if errors remain "
                        "elevated after ten minutes."
                    ),
                }
            ],
        ),
        "answer:customer-status-update": grounded_answer(
            "How quickly do we post a customer status update?",
            (CUSTOMER_COMMS,),
            "Post a customer-visible status update within fifteen minutes.",
            [
                {
                    "document_id": CUSTOMER_COMMS.document_id,
                    "quote": (
                        "Send a customer-visible status update within fifteen "
                        "minutes of confirmed impact."
                    ),
                }
            ],
        ),
    }


def build_dependencies(
    answers: Mapping[str, GroundedAnswer],
) -> dict[str, tuple[KnowledgeDependency, ...]]:
    """Map every derived artifact to its exact consumed source dependencies."""

    artifacts: dict[str, tuple[KnowledgeDependency, ...]] = {
        artifact_id: answer.knowledge_dependencies
        for artifact_id, answer in answers.items()
    }
    artifacts["digest:checkout-runbook"] = (
        KnowledgeDependency(
            document_id=RUNBOOK_V1.document_id,
            revision=RUNBOOK_V1.revision,
        ),
    )
    return artifacts


def _dependency_payload(dependency: KnowledgeDependency) -> dict[str, object]:
    return {
        "dependency_id": dependency.dependency_id,
        "document_id": dependency.document_id,
        "revision": dependency.revision,
        "section_id": dependency.section_id,
        "section_revision": dependency.section_revision,
    }


def _report_payload(report: FreshnessReport) -> dict[str, object]:
    changes = tuple(report.changes)
    return {
        "status": report.status.value,
        "reusable": report.reusable,
        "changes": [
            {
                "dependency_id": change.dependency_id,
                "document_id": change.document_id,
                "section_id": change.section_id,
                "expected_revision": change.expected_revision,
                "current_revision": change.current_revision,
            }
            for change in changes
        ],
        "missing_dependency_ids": list(report.missing_dependency_ids),
        "unversioned_dependency_ids": list(report.unversioned_dependency_ids),
    }


def plan_invalidation(
    artifacts: Mapping[str, tuple[KnowledgeDependency, ...]],
    current_revisions: Mapping[str, str],
    *,
    current_section_revisions: Mapping[tuple[str, str], str] | None = None,
) -> dict[str, object]:
    """Serialize the selective-invalidation decision for the brain."""

    impacts = impacted_artifacts(
        artifacts,
        current_revisions,
        current_section_revisions=current_section_revisions,
    )
    invalidated = tuple(impacts)
    preserved = tuple(sorted(set(artifacts) - set(invalidated)))
    tracked_documents = {
        dependency.document_id
        for dependencies in artifacts.values()
        for dependency in dependencies
    }
    removed_sources = tuple(
        sorted(
            document_id
            for document_id in tracked_documents
            if document_id not in current_revisions
        )
    )
    changed_sections = tuple(
        sorted(
            {
                change.dependency_id
                for report in impacts.values()
                for change in report.changes
                if change.section_id
            }
        )
    )
    return {
        "invalidated": invalidated,
        "preserved": preserved,
        "impacts": {
            art_id: _report_payload(report) for art_id, report in impacts.items()
        },
        "removed_sources": removed_sources,
        "changed_sections": changed_sections,
    }


def _tracked_artifacts(
    artifacts: Mapping[str, tuple[KnowledgeDependency, ...]],
) -> dict[str, list[dict[str, object]]]:
    return {
        artifact_id: [_dependency_payload(row) for row in dependencies]
        for artifact_id, dependencies in artifacts.items()
    }


def _source_payload(document: KnowledgeDocument) -> dict[str, object]:
    return {
        "document_id": document.document_id,
        "source_id": document.source_id,
        "external_id": document.external_id,
        "title": document.title,
        "revision": document.revision,
        "sections": [
            {"section_id": section.section_id, "revision": section.revision}
            for section in document_sections(document)
        ],
    }


def run() -> dict[str, object]:
    """Build the brain, apply one source change set, and return the report."""

    answers = build_answers()
    artifacts = build_dependencies(answers)
    current_documents = (RUNBOOK_V2, INCIDENT_THREAD_V2)
    current_revisions = {
        document.document_id: document.revision for document in current_documents
    }
    current_section_revisions = section_revisions(current_documents)
    plan = plan_invalidation(
        artifacts,
        current_revisions,
        current_section_revisions=current_section_revisions,
    )
    escalation = answers["answer:checkout-escalation"]
    escalation_dependency = escalation.knowledge_dependencies[0]
    return {
        "scenario": "checkout runbook drift with a removed source",
        "sources": [_source_payload(document) for document in current_documents],
        "tracked_artifacts": _tracked_artifacts(artifacts),
        "invalidated": plan["invalidated"],
        "preserved": plan["preserved"],
        "impacts": plan["impacts"],
        "removed_sources": plan["removed_sources"],
        "changed_sections": plan["changed_sections"],
        "unaffected_guidance": {
            "artifact_id": "answer:checkout-escalation",
            "answer": escalation.answer,
            "section_id": escalation_dependency.section_id,
            "section_revision": escalation_dependency.section_revision,
        },
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
