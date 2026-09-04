"""Synchronize revisions, apply host authorization, and retrieve evidence."""

from mari_components import KnowledgeDocument, ScopeRef
from mari_components.platform import InMemoryDocumentStore
from mari_components.retrieval import RevisionBM25Index


def run() -> dict[str, object]:
    scope = ScopeRef(tenant="acme", space="handbook")
    documents = (
        KnowledgeDocument(
            source_id="handbook",
            external_id="refunds",
            title="Refund policy",
            body="Enterprise purchases can be refunded within 30 days.",
            revision="policy-v1",
        ),
        KnowledgeDocument(
            source_id="handbook",
            external_id="payroll",
            title="Payroll",
            body="Payroll closes on the final business day.",
            revision="payroll-v1",
        ),
    )
    store = InMemoryDocumentStore()
    for document in documents:
        store.commit(document, scope=scope, expected_revision=None)

    refs = {document.ref_in(scope): document for document in documents}
    index = RevisionBM25Index({ref: document.body for ref, document in refs.items()})
    allowed_refs = {documents[0].ref_in(scope)}  # supplied by the host authorizer
    hits = index.search("enterprise refund window", limit=5, allowed_refs=allowed_refs)
    selected = refs[hits[0].ref]
    return {
        "document_id": selected.document_id,
        "revision": selected.revision,
        "text": selected.body,
        "score": hits[0].score,
    }


if __name__ == "__main__":
    print(run())
