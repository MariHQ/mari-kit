"""Behavioral tests for the cross-source company search brain example."""

from __future__ import annotations

import json

import pytest

from examples.company_brains.search import (
    CROSS_SOURCE_QUERY,
    EDITED_REFUNDS,
    INITIAL_DOCUMENTS,
    REFUND_QUERY,
    REFUND_QUESTION,
    SCOPE,
    STALE_REFUNDS_EDIT,
    SUPPORT,
    THREAD_QUERY,
    THREAD_QUESTION,
    CompanyBrain,
    host_allowed_refs,
    run,
)
from mari_kit import DocumentACL, KnowledgeDocument, Principal, ScopeRef
from mari_kit.errors import MalformedModelOutput
from mari_kit.knowledge import (
    AnswerDisposition,
    FreshnessStatus,
    assess_freshness,
    parse_answer,
)
from mari_kit.platform import RevisionConflict

FINANCE = Principal(kind="team", identifier="finance")


def _brain_with_initial() -> CompanyBrain:
    brain = CompanyBrain(SCOPE)
    for document in INITIAL_DOCUMENTS:
        brain.commit(document, expected_revision=None)
    return brain


def test_run_is_json_serializable_and_exercises_every_path():
    result = run()
    json.dumps(result)
    assert result["sources"] == ["github:acme/runbooks", "handbook", "slack"]
    assert result["authorization"]["outsider_allowed"] == []
    assert result["retrieval"]["outsider_hits"] == []
    assert result["answers"]["outsider"]["disposition"] == "insufficient_evidence"
    assert result["authorization"]["unauthorized_match_excluded"] is True
    assert result["edit"]["stale_commit_rejected"] is True
    assert result["edit"]["cached_answer_freshness"]["status"] == "stale"
    assert result["deletion"]["cached_answer_freshness"]["status"] == "missing"


def test_support_and_finance_retrieve_different_cross_source_revisions():
    brain = _brain_with_initial()
    support_sources = {
        hit.ref.object.namespace
        for hit in brain.search(CROSS_SOURCE_QUERY, principals=(SUPPORT,))
    }
    finance_sources = {
        hit.ref.object.namespace
        for hit in brain.search(CROSS_SOURCE_QUERY, principals=(FINANCE,))
    }
    assert support_sources == {"handbook", "slack"}
    assert finance_sources == {"handbook", "github:acme/runbooks"}


def test_empty_authorization_returns_no_hits_or_citations():
    brain = _brain_with_initial()
    assert host_allowed_refs(brain.documents, ()) == frozenset()
    assert brain.search(CROSS_SOURCE_QUERY, principals=()) == ()
    answer = brain.answer(REFUND_QUESTION, REFUND_QUERY, principals=())
    assert answer.disposition is AnswerDisposition.INSUFFICIENT_EVIDENCE
    assert answer.evidence == ()


def test_off_topic_question_abstains_even_with_authorized_documents():
    brain = _brain_with_initial()
    assert brain.search("parking policy", principals=(SUPPORT,)) != ()
    answer = brain.answer(
        "Where do visitors park?", "parking policy", principals=(SUPPORT,)
    )
    assert answer.disposition is AnswerDisposition.INSUFFICIENT_EVIDENCE
    assert answer.evidence == ()


def test_unauthorized_matching_document_is_filtered_before_scoring():
    brain = _brain_with_initial()
    github = next(
        document
        for document in INITIAL_DOCUMENTS
        if document.source_id == "github:acme/runbooks"
    )
    ref = github.ref_in(SCOPE)
    explanation = brain.explain(CROSS_SOURCE_QUERY, ref)
    assert explanation is not None and explanation.score > 0
    support_hits = brain.search(CROSS_SOURCE_QUERY, principals=(SUPPORT,))
    assert ref not in {hit.ref for hit in support_hits}


def test_stale_revision_commit_is_rejected_by_compare_and_swap():
    brain = _brain_with_initial()
    brain.commit(EDITED_REFUNDS, expected_revision="handbook-v1")
    with pytest.raises(RevisionConflict):
        brain.commit(STALE_REFUNDS_EDIT, expected_revision="handbook-v1")
    assert brain.current_revisions()["handbook/refunds"] == "handbook-v2"


def test_commit_requires_matching_expected_revision():
    brain = CompanyBrain(SCOPE)
    with pytest.raises(RevisionConflict):
        brain.commit(INITIAL_DOCUMENTS[0], expected_revision="handbook-v1")


def test_edit_invalidates_cached_answer_and_old_retrieval_ref():
    brain = _brain_with_initial()
    answer = brain.answer(REFUND_QUESTION, REFUND_QUERY, principals=(SUPPORT,))
    assert answer.evidence[0].revision == "handbook-v1"

    brain.commit(EDITED_REFUNDS, expected_revision="handbook-v1")

    report = assess_freshness(answer.evidence, brain.current_revisions())
    assert report.status is FreshnessStatus.STALE
    assert not report.reusable

    new_answer = brain.answer(REFUND_QUESTION, REFUND_QUERY, principals=(SUPPORT,))
    assert new_answer.evidence[0].revision == "handbook-v2"
    revisions = {
        hit.ref.revision
        for hit in brain.search(CROSS_SOURCE_QUERY, principals=(SUPPORT,))
    }
    assert "handbook-v1" not in revisions


def test_deletion_drops_live_revision_and_retains_history():
    brain = _brain_with_initial()
    thread_answer = brain.answer(THREAD_QUESTION, THREAD_QUERY, principals=(SUPPORT,))
    assert thread_answer.evidence[0].document_id == "slack/thread:refund-1042"

    removed = brain.delete("slack", "thread:refund-1042")

    assert removed is not None and removed.revision == "slack-v1"
    assert all(
        hit.ref.object.namespace != "slack"
        for hit in brain.search(CROSS_SOURCE_QUERY, principals=(SUPPORT,))
    )
    assert "slack/thread:refund-1042" not in brain.current_revisions()
    report = assess_freshness(thread_answer.evidence, brain.current_revisions())
    assert report.status is FreshnessStatus.MISSING
    assert brain.history("slack", "thread:refund-1042")[0].revision == "slack-v1"


def test_fabricated_citation_is_rejected():
    document = next(
        document for document in INITIAL_DOCUMENTS if document.source_id == "handbook"
    )
    with pytest.raises(MalformedModelOutput):
        parse_answer(
            REFUND_QUESTION,
            (document,),
            {
                "answer": "Refunds are unlimited.",
                "evidence": [
                    {
                        "document_id": document.document_id,
                        "quote": "Refunds are unlimited.",
                    }
                ],
            },
        )


def test_scope_isolation_keeps_tenant_revisions_separate():
    acme = CompanyBrain(SCOPE)
    beta = CompanyBrain(ScopeRef(tenant="beta", space="company"))
    acme.commit(INITIAL_DOCUMENTS[0], expected_revision=None)
    beta.commit(INITIAL_DOCUMENTS[0], expected_revision=None)

    acme.commit(EDITED_REFUNDS, expected_revision="handbook-v1")

    assert acme.current_revisions()["handbook/refunds"] == "handbook-v2"
    assert beta.current_revisions()["handbook/refunds"] == "handbook-v1"


def test_public_visibility_is_authorized_for_any_principal():
    public = KnowledgeDocument(
        source_id="handbook",
        external_id="about",
        title="About",
        body="The company builds knowledge tools.",
        revision="about-v1",
        acl=DocumentACL(visibility="public"),
    )
    allowed = host_allowed_refs((public,), ())
    assert public.ref_in(SCOPE) in allowed
