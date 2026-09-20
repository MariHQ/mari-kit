"""Cross-source company search brain.

This host-owned example composes Mari Kit's structural revision identity,
scope-isolated compare-and-swap document storage, permission-filtered BM25
retrieval, and evidence validation into one company knowledge workflow.

Only the host decides authorization. :func:`host_allowed_refs` is the explicit
policy boundary: retrieval receives the resulting revision set and never sees
provider ACLs. Answer text is quoted from an authorized document and validated
by :func:`mari_kit.knowledge.parse_answer`, so every citation carries an exact
document revision. Edits use compare-and-swap commits; deletions are applied to
the host's live view while scoped revision history is retained.
"""

from __future__ import annotations

import json
from collections.abc import Collection, Iterable

from mari_kit import (
    DocumentACL,
    KnowledgeDocument,
    Principal,
    RevisionRef,
    ScopeRef,
    canonical_document_id,
)
from mari_kit.knowledge import GroundedAnswer, assess_freshness, parse_answer
from mari_kit.platform import InMemoryDocumentStore, RevisionConflict
from mari_kit.retrieval import (
    IndexOperation,
    RevisionBM25Index,
    RevisionIndexDelta,
    RevisionIndexHit,
)

SCOPE = ScopeRef(tenant="acme", space="company")

SUPPORT = Principal(kind="team", identifier="support")
FINANCE = Principal(kind="team", identifier="finance")

# A broad query returns authorized revisions from several provider sources.
CROSS_SOURCE_QUERY = "refund"
REFUND_QUESTION = "How long is the enterprise refund window?"
REFUND_QUERY = "enterprise refund window"
THREAD_QUESTION = "Where are enterprise refund exceptions tracked?"
THREAD_QUERY = "enterprise refund exceptions finance queue"

ABSTENTION_TEXT = "No authorized evidence was retrieved for this question."

INITIAL_DOCUMENTS = (
    KnowledgeDocument(
        source_id="handbook",
        external_id="refunds",
        title="Refund policy",
        body=(
            "Enterprise refund window: purchases can be refunded within 30 days "
            "of invoice."
        ),
        revision="handbook-v1",
        acl=DocumentACL(visibility="restricted", principals=(SUPPORT, FINANCE)),
    ),
    KnowledgeDocument(
        source_id="slack",
        external_id="thread:refund-1042",
        title="Refund exception thread",
        body="Support tracks enterprise refund exceptions in the finance queue.",
        revision="slack-v1",
        acl=DocumentACL(visibility="restricted", principals=(SUPPORT,)),
    ),
    KnowledgeDocument(
        source_id="github:acme/runbooks",
        external_id="billing.md",
        title="Billing runbook",
        body="Finance reviews refund exceptions for requests over 30 days.",
        revision="github-v1",
        acl=DocumentACL(visibility="restricted", principals=(FINANCE,)),
    ),
)

EDITED_REFUNDS = KnowledgeDocument(
    source_id="handbook",
    external_id="refunds",
    title="Refund policy",
    body=(
        "Enterprise refund window: purchases can be refunded within 45 days of invoice."
    ),
    revision="handbook-v2",
    acl=DocumentACL(visibility="restricted", principals=(SUPPORT, FINANCE)),
)

STALE_REFUNDS_EDIT = KnowledgeDocument(
    source_id="handbook",
    external_id="refunds",
    title="Refund policy",
    body=(
        "Enterprise refund window: purchases can be refunded within 60 days of invoice."
    ),
    revision="handbook-v3",
    acl=DocumentACL(visibility="restricted", principals=(SUPPORT, FINANCE)),
)


def host_allowed_refs(
    documents: Iterable[KnowledgeDocument],
    principals: Collection[Principal],
    *,
    scope: ScopeRef = SCOPE,
) -> frozenset[RevisionRef]:
    """Map provider ACL observations and caller principals to allowed revisions.

    This is host policy. Mari records observed visibility but never converts it
    into an access decision, so the application must supply the allowed set.
    """

    identities = frozenset(principals)
    return frozenset(
        document.ref_in(scope)
        for document in documents
        if document.acl.visibility in {"public", "connector_scope"}
        or identities.intersection(document.acl.principals)
    )


class CompanyBrain:
    """A live, scope-isolated company corpus backed by revision storage."""

    def __init__(self, scope: ScopeRef = SCOPE) -> None:
        self.scope = scope
        self._store = InMemoryDocumentStore()
        self._documents: dict[tuple[str, str], KnowledgeDocument] = {}
        self._index = RevisionBM25Index({})

    @property
    def documents(self) -> tuple[KnowledgeDocument, ...]:
        return tuple(self._documents[key] for key in sorted(self._documents))

    def current_revisions(self) -> dict[str, str]:
        return {document.document_id: document.revision for document in self.documents}

    def commit(
        self, document: KnowledgeDocument, *, expected_revision: str | None
    ) -> None:
        """Persist one revision with compare-and-swap, then refresh the index."""

        previous = self._documents.get((document.source_id, document.external_id))
        updated_index = self._index.with_deltas(
            [
                RevisionIndexDelta(
                    ref=document.ref_in(self.scope),
                    previous_ref=previous.ref_in(self.scope) if previous else None,
                    operation=IndexOperation.UPSERT,
                    text=document.body,
                )
            ]
        )
        self._store.commit(
            document, scope=self.scope, expected_revision=expected_revision
        )
        self._documents[(document.source_id, document.external_id)] = document
        self._index = updated_index

    def delete(self, source_id: str, external_id: str) -> KnowledgeDocument | None:
        """Apply a host-owned tombstone to the live view, retaining history."""

        removed = self._documents.get((source_id, external_id))
        if removed is not None:
            self._index = self._index.with_deltas(
                [
                    RevisionIndexDelta(
                        ref=removed.ref_in(self.scope), operation=IndexOperation.DELETE
                    )
                ]
            )
            del self._documents[(source_id, external_id)]
        return removed

    def history(
        self, source_id: str, external_id: str
    ) -> tuple[KnowledgeDocument, ...]:
        return self._store.history(source_id, external_id, scope=self.scope)

    def search(
        self,
        query: str,
        *,
        principals: Collection[Principal],
        limit: int = 5,
    ) -> tuple[RevisionIndexHit, ...]:
        allowed = host_allowed_refs(self.documents, principals, scope=self.scope)
        return self._index.search(query, limit=limit, allowed_refs=allowed)

    def explain(self, query: str, ref: RevisionRef):
        """Expose term contributions so hosts can audit pre-filter behavior."""

        return self._index.explain(query, ref=ref)

    def answer(
        self,
        question: str,
        query: str,
        *,
        principals: Collection[Principal],
        limit: int = 3,
    ) -> GroundedAnswer:
        """Return an exact-quote answer from the top authorized hit, or abstain."""

        hits = self.search(query, principals=principals, limit=limit)
        for hit in hits:
            # BM25 returns every authorized document, including zero-score
            # ones. A grounded answer requires an actual lexical match.
            if hit.score <= 0.0:
                break
            document = self._store.resolve(hit.ref)
            if document is None:
                continue
            quote = document.body.strip()
            return parse_answer(
                question,
                (document,),
                {
                    "answer": quote,
                    "evidence": [{"document_id": document.document_id, "quote": quote}],
                },
            )
        return parse_answer(
            question,
            (),
            {"answer": ABSTENTION_TEXT, "disposition": "insufficient_evidence"},
        )


def _reference_id(ref: RevisionRef) -> str:
    document_id = canonical_document_id(ref.object.namespace, ref.object.object_id)
    return f"{document_id}@{ref.revision}"


def _hit_record(hit: RevisionIndexHit) -> dict[str, object]:
    return {
        "reference": _reference_id(hit.ref),
        "document_id": canonical_document_id(
            hit.ref.object.namespace, hit.ref.object.object_id
        ),
        "revision": hit.ref.revision,
        "score": hit.score,
    }


def _answer_record(answer: GroundedAnswer) -> dict[str, object]:
    return {
        "text": answer.answer,
        "disposition": answer.disposition.value,
        "grounding_coverage": answer.grounding_coverage,
        "citations": [
            {
                "document_id": evidence.document_id,
                "revision": evidence.revision,
                "section_id": evidence.section_id,
                "quote": evidence.quote,
            }
            for evidence in answer.evidence
        ],
    }


def _freshness_record(
    answer: GroundedAnswer, current_revisions: dict[str, str]
) -> dict[str, object]:
    report = assess_freshness(answer.evidence, current_revisions)
    return {
        "status": report.status.value,
        "reusable": report.reusable,
        "changes": [
            {
                "document_id": change.document_id,
                "expected_revision": change.expected_revision,
                "current_revision": change.current_revision,
            }
            for change in report.changes
        ],
        "missing_dependency_ids": list(report.missing_dependency_ids),
    }


def run() -> dict[str, object]:
    """Build the brain, exercise search/answer/edit/delete, return a summary."""

    brain = CompanyBrain(SCOPE)
    for document in INITIAL_DOCUMENTS:
        brain.commit(document, expected_revision=None)

    support_allowed = host_allowed_refs(brain.documents, (SUPPORT,))
    finance_allowed = host_allowed_refs(brain.documents, (FINANCE,))
    outsider_allowed = host_allowed_refs(brain.documents, ())

    support_hits = brain.search(CROSS_SOURCE_QUERY, principals=(SUPPORT,))
    finance_hits = brain.search(CROSS_SOURCE_QUERY, principals=(FINANCE,))
    outsider_hits = brain.search(CROSS_SOURCE_QUERY, principals=())

    refund_answer = brain.answer(REFUND_QUESTION, REFUND_QUERY, principals=(SUPPORT,))
    thread_answer = brain.answer(THREAD_QUESTION, THREAD_QUERY, principals=(SUPPORT,))
    outsider_answer = brain.answer(REFUND_QUESTION, REFUND_QUERY, principals=())

    refund_answer_before_edit = _answer_record(refund_answer)
    refund_freshness_before = _freshness_record(
        refund_answer, brain.current_revisions()
    )

    # An edit is a new revision guarded by compare-and-swap.
    brain.commit(EDITED_REFUNDS, expected_revision="handbook-v1")

    # A concurrent writer based on the stale v1 revision must be rejected.
    stale_error = ""
    try:
        brain.commit(STALE_REFUNDS_EDIT, expected_revision="handbook-v1")
    except RevisionConflict as error:
        stale_error = str(error)

    refund_answer_after_edit = brain.answer(
        REFUND_QUESTION, REFUND_QUERY, principals=(SUPPORT,)
    )
    refund_freshness_after_edit = _freshness_record(
        refund_answer, brain.current_revisions()
    )
    hits_after_edit = brain.search(CROSS_SOURCE_QUERY, principals=(SUPPORT,))

    # A deletion removes the live revision from retrieval while history remains.
    deleted = brain.delete("slack", "thread:refund-1042")
    hits_after_delete = brain.search(CROSS_SOURCE_QUERY, principals=(SUPPORT,))
    thread_freshness_after_delete = _freshness_record(
        thread_answer, brain.current_revisions()
    )
    retained_history = brain.history("slack", "thread:refund-1042")

    github_ref = next(
        document.ref_in(SCOPE)
        for document in INITIAL_DOCUMENTS
        if document.source_id == "github:acme/runbooks"
    )
    explanation = brain.explain(CROSS_SOURCE_QUERY, github_ref)
    unauthorized_match_excluded = (
        explanation is not None
        and explanation.score > 0
        and github_ref not in {hit.ref for hit in support_hits}
    )

    return {
        "scope": {"tenant": SCOPE.tenant, "space": SCOPE.space},
        "sources": sorted({document.source_id for document in INITIAL_DOCUMENTS}),
        "authorization": {
            "support_allowed": sorted(_reference_id(ref) for ref in support_allowed),
            "finance_allowed": sorted(_reference_id(ref) for ref in finance_allowed),
            "outsider_allowed": sorted(_reference_id(ref) for ref in outsider_allowed),
            "unauthorized_match_excluded": unauthorized_match_excluded,
            "unauthorized_match_score": (
                explanation.score if explanation is not None else 0.0
            ),
        },
        "retrieval": {
            "cross_source_query": CROSS_SOURCE_QUERY,
            "support_hits": [_hit_record(hit) for hit in support_hits],
            "finance_hits": [_hit_record(hit) for hit in finance_hits],
            "outsider_hits": [_hit_record(hit) for hit in outsider_hits],
        },
        "answers": {
            "refund": refund_answer_before_edit,
            "refund_freshness": refund_freshness_before,
            "thread": _answer_record(thread_answer),
            "outsider": _answer_record(outsider_answer),
        },
        "edit": {
            "from_revision": "handbook-v1",
            "to_revision": "handbook-v2",
            "stale_commit_rejected": bool(stale_error),
            "stale_commit_error": stale_error,
            "cached_answer_freshness": refund_freshness_after_edit,
            "answer_after_edit": _answer_record(refund_answer_after_edit),
            "hits_after_edit": [_hit_record(hit) for hit in hits_after_edit],
        },
        "deletion": {
            "deleted_document_id": (deleted.document_id if deleted is not None else ""),
            "hits_after_delete": [_hit_record(hit) for hit in hits_after_delete],
            "cached_answer_freshness": thread_freshness_after_delete,
            "history_revisions": [document.revision for document in retained_history],
        },
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
