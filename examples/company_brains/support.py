"""Customer support company brain with reviewed answer and workflow caching.

The host owns documents, principal-to-document authorization, query embeddings,
the agent/LLM round, and persistence. Mari Kit owns the reviewed-intent index,
cache and freshness decisions, evidence validation, and change-impact reports.

``run()`` is credential-free and deterministic. It exercises valid reuse, a
changed source, a newly relevant document, revoked access, an unanswered
question, a cold reviewed intent (no cached answer yet), and a below-threshold
near miss, then returns JSON-serializable results.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Collection, Iterable, Mapping

from mari_kit import DocumentACL, KnowledgeDocument, Principal
from mari_kit.knowledge import (
    KnowledgeDependency,
    impacted_artifacts,
    parse_answer,
    section_revisions,
)
from mari_kit.trajectories import (
    ReviewedWorkflow,
    WorkflowAction,
    WorkflowDecision,
    WorkflowPolicy,
    build_reviewed_workflow_index,
    decide_reviewed_workflow,
    match_cached_response,
    start_speculative_retrieval,
)

SUPPORT_VOICE = KnowledgeDocument(
    source_id="support:kb",
    external_id="support-voice",
    title="Support voice",
    body=(
        "# Support voice\n\n"
        "Be warm, direct, and concise. Lead with the answer and avoid "
        "exclamation points."
    ),
    revision="voice-v4",
    acl=DocumentACL(
        visibility="restricted",
        principals=(Principal(kind="team", identifier="support"),),
    ),
)
ENTERPRISE_REFUND_POLICY = KnowledgeDocument(
    source_id="support:kb",
    external_id="enterprise-refund-policy",
    title="Enterprise refund policy",
    body=(
        "# Enterprise refund policy\n\n"
        "## Refund window\n"
        "Enterprise customers may request a full refund within 30 days of "
        "purchase.\n\n"
        "## Renewal terms\n"
        "Enterprise contracts renew annually unless cancelled 45 days before "
        "renewal."
    ),
    revision="refund-v1",
    acl=DocumentACL(
        visibility="restricted",
        principals=(Principal(kind="team", identifier="enterprise-support"),),
    ),
)
SHIPPING_POLICY = KnowledgeDocument(
    source_id="support:kb",
    external_id="shipping-policy",
    title="Shipping policy",
    body=(
        "# Shipping policy\n\n"
        "## Delivery windows\n"
        "Standard delivery arrives within five business days."
    ),
    revision="shipping-v2",
    acl=DocumentACL(visibility="public"),
)
PASSWORD_RESET_GUIDE = KnowledgeDocument(
    source_id="support:kb",
    external_id="password-reset",
    title="Password reset guide",
    body=(
        "# Password reset\n\n"
        "## Reset steps\n"
        "Open account settings and choose Reset password."
    ),
    revision="password-v1",
    acl=DocumentACL(visibility="public"),
)

DOCUMENTS = (
    SUPPORT_VOICE,
    ENTERPRISE_REFUND_POLICY,
    SHIPPING_POLICY,
    PASSWORD_RESET_GUIDE,
)

REFUND_INTENT = (1.0, 0.0, 0.0, 0.0)
UNANSWERED_INTENT = (0.0, 1.0, 0.0, 0.0)
SHIPPING_INTENT = (0.0, 0.0, 1.0, 0.0)
PASSWORD_INTENT = (0.0, 0.0, 0.0, 1.0)
NEAR_MISS_INTENT = (0.70, 0.30, 0.0, 0.0)

ENTERPRISE_REFUND_QUESTION = (
    "How long do enterprise customers have to request a refund?"
)
SHIPPING_QUESTION = "How quickly does standard delivery arrive?"
UNANSWERED_QUESTION = "Do you offer a loyalty discount for bicycles?"

REFUND_QUOTE = (
    "Enterprise customers may request a full refund within 30 days of purchase."
)
SHIPPING_QUOTE = "Standard delivery arrives within five business days."

REVIEWED_REFUND_ANSWER = parse_answer(
    ENTERPRISE_REFUND_QUESTION,
    DOCUMENTS,
    {
        "answer": (
            "Absolutely. Enterprise customers may request a full refund within "
            "30 days of purchase."
        ),
        "disposition": "grounded",
        "evidence": [
            {"document_id": ENTERPRISE_REFUND_POLICY.document_id, "quote": REFUND_QUOTE}
        ],
    },
    context_dependencies=(
        KnowledgeDependency(
            document_id=SUPPORT_VOICE.document_id,
            revision=SUPPORT_VOICE.revision,
        ),
    ),
)
REVIEWED_SHIPPING_ANSWER = parse_answer(
    SHIPPING_QUESTION,
    DOCUMENTS,
    {
        "answer": "Standard delivery arrives within five business days.",
        "disposition": "grounded",
        "evidence": [
            {"document_id": SHIPPING_POLICY.document_id, "quote": SHIPPING_QUOTE}
        ],
    },
)
REVIEWED_WORKFLOWS = (
    ReviewedWorkflow(
        identifier="support-refund",
        name="Answer enterprise refund policy questions",
        match_vectors=(REFUND_INTENT, (0.90, 0.10, 0.0, 0.0)),
        document_ids=(
            ENTERPRISE_REFUND_POLICY.document_id,
            SUPPORT_VOICE.document_id,
        ),
        cached_answer=REVIEWED_REFUND_ANSWER,
    ),
    ReviewedWorkflow(
        identifier="support-shipping",
        name="Answer standard shipping questions",
        match_vectors=(SHIPPING_INTENT,),
        document_ids=(SHIPPING_POLICY.document_id,),
        cached_answer=REVIEWED_SHIPPING_ANSWER,
    ),
    ReviewedWorkflow(
        identifier="support-password-reset",
        name="Walk a customer through a password reset",
        match_vectors=(PASSWORD_INTENT,),
        document_ids=(PASSWORD_RESET_GUIDE.document_id,),
    ),
)
WORKFLOW_INDEX = build_reviewed_workflow_index(REVIEWED_WORKFLOWS)
POLICY = WorkflowPolicy()

ENTERPRISE_REFUND_POLICY_V2 = KnowledgeDocument(
    source_id=ENTERPRISE_REFUND_POLICY.source_id,
    external_id=ENTERPRISE_REFUND_POLICY.external_id,
    title=ENTERPRISE_REFUND_POLICY.title,
    body=ENTERPRISE_REFUND_POLICY.body.replace(
        "30 days of purchase", "60 days of purchase"
    ),
    revision="refund-v2",
)
ENTERPRISE_REFUND_POLICY_V3 = KnowledgeDocument(
    source_id=ENTERPRISE_REFUND_POLICY.source_id,
    external_id=ENTERPRISE_REFUND_POLICY.external_id,
    title=ENTERPRISE_REFUND_POLICY.title,
    body=ENTERPRISE_REFUND_POLICY.body.replace(
        "45 days before renewal", "60 days before renewal"
    ),
    revision="refund-v3",
)
REFUND_EXCEPTIONS = KnowledgeDocument(
    source_id="support:kb",
    external_id="enterprise-refund-exceptions",
    title="Enterprise refund exceptions",
    body=(
        "# Enterprise refund exceptions\n\n"
        "## Hardware bundles\n"
        "Refunds for bundled hardware follow the hardware warranty terms."
    ),
    revision="exceptions-v1",
    acl=DocumentACL(
        visibility="restricted",
        principals=(Principal(kind="team", identifier="enterprise-support"),),
    ),
)


def allowed_document_ids(
    principals: Collection[Principal],
    documents: Iterable[KnowledgeDocument] = DOCUMENTS,
) -> frozenset[str]:
    """Host authorization: map provider ACL observations to visible documents."""
    identities = frozenset(principals)
    return frozenset(
        document.document_id
        for document in documents
        if document.acl.visibility == "public"
        or bool(identities.intersection(document.acl.principals))
    )


def _decision(
    query: tuple[float, ...],
    revisions: Mapping[str, str],
    sections: Mapping[tuple[str, str], str],
    *,
    allowed: Collection[str],
    relevant_scores: Mapping[str, float] | None = None,
    impact_decisions: Mapping[str, bool] | None = None,
) -> WorkflowDecision:
    return decide_reviewed_workflow(
        (query,),
        WORKFLOW_INDEX,
        revisions,
        current_section_revisions=sections,
        allowed_document_ids=allowed,
        relevant_document_scores=relevant_scores,
        impact_decisions=impact_decisions,
        policy=POLICY,
    )


def _summary(decision: WorkflowDecision) -> dict[str, object]:
    answer = decision.cached_answer
    return {
        "action": decision.action.value,
        "reason": decision.reason.value,
        "workflow_id": decision.match.workflow.identifier if decision.match else "",
        "score": round(decision.match.score, 4) if decision.match else None,
        "cached_answer": answer.answer if answer else None,
        "documents_needing_impact_review": decision.documents_needing_impact_review,
        "document_ids": decision.document_ids,
    }


async def _await_speculative_read(
    decision: WorkflowDecision,
    documents_by_id: Mapping[str, KnowledgeDocument],
) -> tuple[bool, tuple[str, ...]]:
    started = asyncio.Event()

    async def retrieve(document_ids: tuple[str, ...]) -> tuple[KnowledgeDocument, ...]:
        started.set()
        await asyncio.sleep(0)
        return tuple(documents_by_id[document_id] for document_id in document_ids)

    task = start_speculative_retrieval(decision, retrieve)
    await started.wait()
    started_before_await = not task.done()
    documents = await task
    return started_before_await, tuple(document.document_id for document in documents)


def _speculative_read(
    decision: WorkflowDecision,
    documents_by_id: Mapping[str, KnowledgeDocument],
) -> tuple[bool, tuple[str, ...]]:
    return asyncio.run(_await_speculative_read(decision, documents_by_id))


def run() -> dict[str, object]:
    """Exercise the support cache in one deterministic, credential-free pass."""
    current_revisions = {
        document.document_id: document.revision for document in DOCUMENTS
    }
    current_sections = section_revisions(DOCUMENTS)
    enterprise_agent = (
        Principal(kind="team", identifier="support"),
        Principal(kind="team", identifier="enterprise-support"),
    )
    enterprise_allowed = allowed_document_ids(enterprise_agent)

    reuse = _decision(
        REFUND_INTENT,
        current_revisions,
        current_sections,
        allowed=enterprise_allowed,
    )
    reuse_cache = match_cached_response(
        (REFUND_INTENT,),
        WORKFLOW_INDEX,
        current_revisions,
        minimum_score=POLICY.cache_threshold,
        current_section_revisions=current_sections,
        allowed_document_ids=enterprise_allowed,
    )
    changed_revisions = {
        **current_revisions,
        ENTERPRISE_REFUND_POLICY.document_id: ENTERPRISE_REFUND_POLICY_V2.revision,
    }
    changed_sections = {
        **current_sections,
        **section_revisions((ENTERPRISE_REFUND_POLICY_V2,)),
    }
    changed = _decision(
        REFUND_INTENT,
        changed_revisions,
        changed_sections,
        allowed=enterprise_allowed,
    )
    current_by_id = {document.document_id: document for document in DOCUMENTS}
    changed_by_id = {
        **current_by_id,
        ENTERPRISE_REFUND_POLICY_V2.document_id: ENTERPRISE_REFUND_POLICY_V2,
    }
    speculative_started, speculatively_read = _speculative_read(changed, changed_by_id)
    changed_impacts = impacted_artifacts(
        {
            "workflow:support-refund": REVIEWED_REFUND_ANSWER.knowledge_dependencies,
            "workflow:support-shipping": REVIEWED_SHIPPING_ANSWER.knowledge_dependencies,
        },
        changed_revisions,
        current_section_revisions=changed_sections,
    )
    shipping_after_change = _decision(
        SHIPPING_INTENT,
        changed_revisions,
        changed_sections,
        allowed=enterprise_allowed,
    )
    voice_revisions = {
        **current_revisions,
        SUPPORT_VOICE.document_id: "voice-v5",
    }
    voice_changed = _decision(
        REFUND_INTENT,
        voice_revisions,
        current_sections,
        allowed=enterprise_allowed,
    )

    unrelated_revisions = {
        **current_revisions,
        ENTERPRISE_REFUND_POLICY.document_id: ENTERPRISE_REFUND_POLICY_V3.revision,
    }
    unrelated_sections = {
        **current_sections,
        **section_revisions((ENTERPRISE_REFUND_POLICY_V3,)),
    }
    selective = _decision(
        REFUND_INTENT,
        unrelated_revisions,
        unrelated_sections,
        allowed=enterprise_allowed,
    )
    whole_document_only = _decision(
        REFUND_INTENT,
        unrelated_revisions,
        {},
        allowed=enterprise_allowed,
    )

    new_document_id = REFUND_EXCEPTIONS.document_id
    new_document_allowed = enterprise_allowed | {new_document_id}
    relevant_scores = {new_document_id: 0.99}
    new_unreviewed = _decision(
        REFUND_INTENT,
        current_revisions,
        current_sections,
        allowed=new_document_allowed,
        relevant_scores=relevant_scores,
    )
    new_nonimpacting = _decision(
        REFUND_INTENT,
        current_revisions,
        current_sections,
        allowed=new_document_allowed,
        relevant_scores=relevant_scores,
        impact_decisions={new_document_id: False},
    )
    new_impacting = _decision(
        REFUND_INTENT,
        current_revisions,
        current_sections,
        allowed=new_document_allowed,
        relevant_scores=relevant_scores,
        impact_decisions={new_document_id: True},
    )

    support_only_allowed = allowed_document_ids(
        (Principal(kind="team", identifier="support"),)
    )
    revoked = _decision(
        REFUND_INTENT,
        current_revisions,
        current_sections,
        allowed=support_only_allowed,
    )
    revoked_cache = match_cached_response(
        (REFUND_INTENT,),
        WORKFLOW_INDEX,
        current_revisions,
        minimum_score=POLICY.cache_threshold,
        current_section_revisions=current_sections,
        allowed_document_ids=support_only_allowed,
    )

    unanswered = _decision(
        UNANSWERED_INTENT,
        current_revisions,
        current_sections,
        allowed=enterprise_allowed,
    )
    cold = _decision(
        PASSWORD_INTENT,
        current_revisions,
        current_sections,
        allowed=enterprise_allowed,
    )
    near_miss = _decision(
        NEAR_MISS_INTENT,
        current_revisions,
        current_sections,
        allowed=enterprise_allowed,
    )

    revoked_answer = revoked.cached_answer.answer if revoked.cached_answer else ""
    return {
        "company": "customer-support",
        "credential_free": True,
        "policy": {
            "speculation_threshold": POLICY.speculation_threshold,
            "cache_threshold": POLICY.cache_threshold,
            "relevant_document_threshold": POLICY.relevant_document_threshold,
        },
        "documents": tuple(
            {
                "document_id": document.document_id,
                "title": document.title,
                "revision": document.revision,
                "visibility": document.acl.visibility,
            }
            for document in DOCUMENTS
        ),
        "reviewed_workflows": tuple(
            {
                "workflow_id": workflow.identifier,
                "name": workflow.name,
                "document_ids": workflow.document_ids,
                "cached": workflow.cached_answer is not None,
            }
            for workflow in REVIEWED_WORKFLOWS
        ),
        "valid_reuse": {
            **_summary(reuse),
            "cache_reusable": reuse_cache.reusable,
            "cache_reason": reuse_cache.reason.value,
            "served_reviewed_answer": reuse.cached_answer is REVIEWED_REFUND_ANSWER,
        },
        "changed_source": {
            **_summary(changed),
            "changed_document_id": ENTERPRISE_REFUND_POLICY.document_id,
            "cited_section_id": REVIEWED_REFUND_ANSWER.evidence[0].section_id,
            "impacted_artifacts": tuple(changed_impacts),
            "shipping_reused_after_change": (
                shipping_after_change.action is WorkflowAction.CACHED_RESPONSE
            ),
            "changed_context_voice_action": voice_changed.action.value,
        },
        "unrelated_source_edit": {
            "changed_document_id": ENTERPRISE_REFUND_POLICY.document_id,
            "with_section_revisions": selective.action.value,
            "with_section_revisions_reason": selective.reason.value,
            "whole_document_fallback": whole_document_only.action.value,
            "whole_document_fallback_reason": whole_document_only.reason.value,
        },
        "relevant_new_document": {
            "new_document_id": new_document_id,
            "unresolved": _summary(new_unreviewed),
            "nonimpacting": _summary(new_nonimpacting),
            "impacting": _summary(new_impacting),
        },
        "revoked_access": {
            "allowed_document_ids": tuple(sorted(support_only_allowed)),
            "restricted_document_id": ENTERPRISE_REFUND_POLICY.document_id,
            **_summary(revoked),
            "cache_reusable": revoked_cache.reusable,
            "cache_reason": revoked_cache.reason.value,
            "cached_answer_returned": bool(revoked_answer),
        },
        "unanswered_question": {
            "question": UNANSWERED_QUESTION,
            **_summary(unanswered),
        },
        "cold_reviewed_intent": {
            "question": "How do I reset my password?",
            **_summary(cold),
        },
        "below_cache_threshold": {
            "score": (round(near_miss.match.score, 4) if near_miss.match else None),
            **_summary(near_miss),
        },
        "speculative_retrieval": {
            "started_before_await": speculative_started,
            "read_document_ids": speculatively_read,
        },
        "host_responsibilities": (
            "documents and revisions",
            "principal-to-document authorization",
            "query embeddings and relevance scores",
            "the actual agent/LLM answer round",
            "persistence of reviewed answers and cache state",
        ),
        "library_responsibilities": (
            "reviewed-intent MUVERA index and exact reranking",
            "cache/freshness decisions and conservative gates",
            "evidence validation and dependency tracking",
            "change-impact reports for cached artifacts",
        ),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
