"""Multi-tenant company brain isolated by scope, ACL, and evidence boundaries.

Two tenants hold documents with *identical* ``source_id`` and ``external_id``
values, so their structural ``document_id`` values collide. This module shows
which Mari Kit boundaries keep them apart (scoped stores, scoped revision
retrieval, scoped located evidence) and which boundaries trust the host to keep
them apart (``allowed_refs``/``allowed_document_ids``, bare-document parsers).

Run without credentials::

    python -m examples.company_brains.isolation
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Collection, Iterable
from dataclasses import dataclass

import numpy as np

from mari_kit import (
    DocumentACL,
    Evidence,
    KnowledgeDocument,
    Principal,
    RevisionRef,
    ScopeRef,
)
from mari_kit.errors import MalformedModelOutput
from mari_kit.knowledge import (
    Activity,
    KnowledgeArtifact,
    KnowledgeScope,
    document_evidence_ref,
    parse_answer,
    validate_located_evidence,
)
from mari_kit.platform import InMemoryArtifactStore, InMemoryDocumentStore
from mari_kit.references import LocatedEvidence, ObjectRef
from mari_kit.retrieval import RevisionBM25Index, build_index, search_index

SPACE = "company-brain"
SHARED_SOURCE = "confluence:acme"
REFUND_EXTERNAL = "page:refunds"
STATUS_EXTERNAL = "page:status"
QUESTION = "How long are enterprise refunds?"
QUERY = "enterprise refunds issued"

TENANT_A = ScopeRef(tenant="tenant-a", space=SPACE)
TENANT_B = ScopeRef(tenant="tenant-b", space=SPACE)

# Same source_id/external_id in both tenants: the structural document_id is
# identical and only the enclosing scope distinguishes the records.
REFUNDS_A = KnowledgeDocument(
    source_id=SHARED_SOURCE,
    external_id=REFUND_EXTERNAL,
    title="Refund policy",
    body="Tenant A enterprise refunds are issued within 30 days.",
    revision="a-refunds-1",
    acl=DocumentACL(
        visibility="restricted",
        principals=(Principal(kind="team", identifier="finance"),),
    ),
)
STATUS_A = KnowledgeDocument(
    source_id=SHARED_SOURCE,
    external_id=STATUS_EXTERNAL,
    title="Service status",
    body="Tenant A status: the checkout service is operating normally.",
    revision="a-status-1",
    acl=DocumentACL(visibility="public"),
)
REFUNDS_B = KnowledgeDocument(
    source_id=SHARED_SOURCE,
    external_id=REFUND_EXTERNAL,
    title="Refund policy",
    body="Tenant B enterprise refunds are issued within 14 days.",
    revision="b-refunds-1",
    acl=DocumentACL(
        visibility="restricted",
        principals=(Principal(kind="team", identifier="support"),),
    ),
)
STATUS_B = KnowledgeDocument(
    source_id=SHARED_SOURCE,
    external_id=STATUS_EXTERNAL,
    title="Service status",
    body="Tenant B status: the billing service is operating normally.",
    revision="b-status-1",
    acl=DocumentACL(visibility="public"),
)

DOCUMENTS: dict[str, tuple[KnowledgeDocument, ...]] = {
    "tenant-a": (REFUNDS_A, STATUS_A),
    "tenant-b": (REFUNDS_B, STATUS_B),
}

_DOCUMENT_INDEX = {
    (tenant, document.source_id, document.external_id): document
    for tenant, documents in DOCUMENTS.items()
    for document in documents
}


@dataclass(frozen=True, slots=True)
class User:
    """A host user: the tenant wall plus the provider principals they hold."""

    identifier: str
    tenant: str
    principals: tuple[Principal, ...]


ALICE = User("alice", "tenant-a", (Principal(kind="team", identifier="finance"),))
CAROL = User("carol", "tenant-a", ())
BOB = User("bob", "tenant-b", (Principal(kind="team", identifier="support"),))


def _visible_to(acl: DocumentACL, principals: Collection[Principal]) -> bool:
    if acl.visibility == "public":
        return True
    return bool(frozenset(principals) & set(acl.principals))


class TenantAuthorizer:
    """Host authorization boundary: tenant wall first, then ACL observation.

    The tenant wall is enforced structurally. A reference outside the user's
    tenant is denied before any ACL metadata is consulted, so an unknown or
    forged cross-tenant identity cannot be authorized by matching principals.
    """

    def __init__(self, user: User) -> None:
        self._user = user

    def __call__(self, principal: Collection[Principal], ref: ObjectRef) -> bool:
        scope = ref.scope
        if scope is None or scope.tenant != self._user.tenant:
            return False
        document = _DOCUMENT_INDEX.get((scope.tenant, ref.namespace, ref.object_id))
        if document is None:
            return False
        return _visible_to(document.acl, principal)


class CompanyBrain:
    """Scoped stores, scoped retrieval, and evidence validation for tenants."""

    def __init__(self) -> None:
        self.scopes = {"tenant-a": TENANT_A, "tenant-b": TENANT_B}
        self.documents = DOCUMENTS
        self.document_store = InMemoryDocumentStore()
        for tenant, documents in DOCUMENTS.items():
            for document in documents:
                self.document_store.commit(
                    document, scope=self.scopes[tenant], expected_revision=None
                )
        self.artifact_store = InMemoryArtifactStore()
        self.index = RevisionBM25Index(
            {
                document.ref_in(self.scopes[tenant]): (
                    f"{document.title} {document.body}"
                )
                for tenant, documents in DOCUMENTS.items()
                for document in documents
            }
        )

    def authorized_documents(self, user: User) -> tuple[KnowledgeDocument, ...]:
        return tuple(
            document
            for document in DOCUMENTS[user.tenant]
            if _visible_to(document.acl, user.principals)
        )

    def authorized_refs(self, user: User) -> frozenset[RevisionRef]:
        scope = self.scopes[user.tenant]
        return frozenset(
            document.ref_in(scope) for document in self.authorized_documents(user)
        )

    def search(self, user: User, query: str, *, limit: int = 10):
        return self.index.search(
            query, limit=limit, allowed_refs=self.authorized_refs(user)
        )

    def resolve_body(self, ref: RevisionRef) -> str | None:
        document = self.document_store.resolve(ref)
        return document.body if document is not None else None

    def commit_answer(
        self, user: User, answer_text: str, evidence: Iterable[LocatedEvidence]
    ) -> KnowledgeArtifact[dict[str, str]]:
        scope: KnowledgeScope = self.scopes[user.tenant]
        artifact = KnowledgeArtifact(
            artifact_id="answer:refunds",
            revision="v1",
            value={"question": QUESTION, "answer": answer_text},
            scope=scope,
            recorded_at=dt.datetime(2024, 1, 1, tzinfo=dt.UTC),
            generated_by=Activity(identifier="answer", implementation="company-brain"),
            evidence=tuple(evidence),
        )
        self.artifact_store.commit(artifact, expected_revision=None)
        return artifact


def _scope_label(ref: RevisionRef) -> str:
    scope = ref.object.scope
    tenant = scope.tenant if scope else ""
    return f"{tenant}::{ref.object.namespace}/{ref.object.object_id}@{ref.revision}"


def _hits(hits) -> list[dict[str, object]]:
    return [
        {
            "ref": _scope_label(hit.ref),
            "tenant": hit.ref.object.scope.tenant,
            "score": round(hit.score, 6),
        }
        for hit in hits
    ]


def _alice_answer():
    return parse_answer(
        QUESTION,
        (REFUNDS_A, STATUS_A),
        {
            "answer": "Tenant A enterprise refunds are issued within 30 days.",
            "evidence": [
                {
                    "document_id": REFUNDS_A.document_id,
                    "quote": REFUNDS_A.body,
                }
            ],
        },
    )


def _accepts_evidence(
    documents: tuple[KnowledgeDocument, ...],
) -> bool:
    """Probe whether parse_answer binds evidence under a merged document set."""

    try:
        parse_answer(
            QUESTION,
            documents,
            {
                "answer": REFUNDS_B.body,
                "evidence": [
                    {"document_id": REFUNDS_B.document_id, "quote": REFUNDS_B.body}
                ],
            },
        )
    except (MalformedModelOutput, ValueError):
        return False
    return True


def run() -> dict[str, object]:
    brain = CompanyBrain()

    scopes = [TENANT_A, TENANT_B]
    document_id_collision = {
        "document_id": REFUNDS_A.document_id,
        "same_id_in_both_tenants": REFUNDS_A.document_id == REFUNDS_B.document_id,
        "bodies_differ": REFUNDS_A.body != REFUNDS_B.body,
        "refs_distinct": REFUNDS_A.ref_in(TENANT_A) != REFUNDS_B.ref_in(TENANT_B),
    }

    store = brain.document_store
    cross_scope_ref = RevisionRef(
        object=ObjectRef(
            namespace=SHARED_SOURCE,
            object_id=REFUND_EXTERNAL,
            scope=ScopeRef(tenant="tenant-c", space=SPACE),
        ),
        revision=REFUNDS_A.revision,
    )
    scoped_store = {
        "tenant_a_refund_body": store.get(
            SHARED_SOURCE, REFUND_EXTERNAL, scope=TENANT_A
        ).body,
        "tenant_b_refund_body": store.get(
            SHARED_SOURCE, REFUND_EXTERNAL, scope=TENANT_B
        ).body,
        "cross_scope_lookup_is_none": store.get(
            SHARED_SOURCE, REFUND_EXTERNAL, scope=ScopeRef(tenant="tenant-c")
        )
        is None,
        "tenant_a_ref_resolves_to_a": store.resolve(REFUNDS_A.ref_in(TENANT_A)).body
        == REFUNDS_A.body,
        "tenant_b_ref_never_resolves_in_a": store.resolve(REFUNDS_B.ref_in(TENANT_A))
        is None,
        "unknown_scope_ref_is_none": store.resolve(cross_scope_ref) is None,
        "identical_revision_kept_per_tenant": (
            store.history(SHARED_SOURCE, REFUND_EXTERNAL, scope=TENANT_A)
            == (REFUNDS_A,)
            and store.history(SHARED_SOURCE, REFUND_EXTERNAL, scope=TENANT_B)
            == (REFUNDS_B,)
        ),
    }

    users = {"alice": ALICE, "carol": CAROL, "bob": BOB}
    authorization = {
        name: {
            "tenant": user.tenant,
            "principals": [f"{row.kind}:{row.identifier}" for row in user.principals],
            "allowed_refs": sorted(
                _scope_label(ref) for ref in brain.authorized_refs(user)
            ),
        }
        for name, user in users.items()
    }

    retrieval = {name: _hits(brain.search(user, QUERY)) for name, user in users.items()}
    every_hit_in_user_tenant = all(
        all(hit["tenant"] == user.tenant for hit in retrieval[name])
        for name, user in users.items()
    )
    contractor_ref = _scope_label(REFUNDS_A.ref_in(TENANT_A))
    restricted_refund_hidden_from_contractor = (
        contractor_ref not in brain.authorized_refs(CAROL)
        and contractor_ref not in {hit["ref"] for hit in retrieval["carol"]}
    )

    # The index applies the host's authorization set verbatim. Supplying refs
    # from two tenants returns both, so hosts must derive allowed_refs, never
    # accept them from request input.
    cross_tenant_refs = brain.authorized_refs(ALICE) | brain.authorized_refs(BOB)
    host_supplied_refs_are_trusted = {
        _scope_label(hit.ref)
        for hit in brain.index.search(QUERY, limit=10, allowed_refs=cross_tenant_refs)
    } == {_scope_label(ref) for ref in cross_tenant_refs}

    # The vector index is keyed by bare document_id, so identical IDs in two
    # tenants collapse at the host boundary before build_index sees them.
    unscoped = dict(
        (document.document_id, _tiny_vector(document))
        for documents in DOCUMENTS.values()
        for document in documents
    )
    unscoped_index = build_index(unscoped)
    unscoped_collapse = {
        "ids_before": len(DOCUMENTS["tenant-a"]) + len(DOCUMENTS["tenant-b"]),
        "ids_indexed": len(unscoped_index.document_ids),
    }
    tenant_qualified = {
        f"{tenant}::{document.document_id}": _tiny_vector(document)
        for tenant, documents in DOCUMENTS.items()
        for document in documents
    }
    qualified_index = build_index(tenant_qualified)
    alice_vector_query = np.asarray([[1.0, 0.0, 0.0]], np.float32)
    alice_allowed_ids = {
        f"tenant-a::{document.document_id}"
        for document in brain.authorized_documents(ALICE)
    }
    vector_hits = [
        hit.document_id
        for hit in search_index(
            qualified_index,
            alice_vector_query,
            limit=10,
            allowed_document_ids=alice_allowed_ids,
        )
    ]

    answer = _alice_answer()
    safe_evidence = (
        LocatedEvidence(ref=REFUNDS_A.ref_in(TENANT_A), quote=REFUNDS_A.body),
    )
    safe_report = validate_located_evidence(
        safe_evidence,
        resolve_material=brain.resolve_body,
        visible_refs=brain.authorized_refs(ALICE),
    )
    cross_tenant_evidence = (
        LocatedEvidence(ref=REFUNDS_B.ref_in(TENANT_B), quote=REFUNDS_B.body),
    )
    guarded_report = validate_located_evidence(
        cross_tenant_evidence,
        resolve_material=brain.resolve_body,
        visible_refs=brain.authorized_refs(ALICE),
    )
    unguarded_report = validate_located_evidence(
        cross_tenant_evidence,
        resolve_material=brain.resolve_body,
        visible_refs=None,
    )
    evidence = {
        "alice_grounded_answer": answer.answer,
        "alice_evidence_document_ids": [row.document_id for row in answer.evidence],
        "alice_evidence_quote_matches_tenant_a": all(
            row.quote == REFUNDS_A.body for row in answer.evidence
        ),
        "scoped_evidence_accepted": safe_report.accepted,
        "cross_tenant_evidence_rejected": (
            not guarded_report.accepted
            and {issue.kind.value for issue in guarded_report.issues} == {"not_visible"}
        ),
        "missing_visible_refs_admits_cross_tenant": unguarded_report.accepted,
    }

    # Ambiguous document IDs must be rejected regardless of input order.
    merged_ab = _accepts_evidence((REFUNDS_A, REFUNDS_B))
    merged_ba = _accepts_evidence((REFUNDS_B, REFUNDS_A))
    parser_collapse = {
        "accepts_second_tenant_when_last": merged_ab,
        "rejects_second_tenant_when_first": not merged_ba,
        "order_dependent_acceptance": merged_ab != merged_ba,
        "ambiguous_documents_rejected": not merged_ab and not merged_ba,
        "shared_document_id": REFUNDS_A.document_id,
    }

    artifact = brain.commit_answer(ALICE, answer.answer, safe_evidence)
    artifacts = {
        "tenant_a_artifact": dict(artifact.value),
        "tenant_b_get_is_none": brain.artifact_store.get(
            "answer:refunds", scope=TENANT_B
        )
        is None,
        "tenant_b_history_is_empty": brain.artifact_store.history(
            "answer:refunds", scope=TENANT_B
        )
        == (),
        "tenant_b_at_time_is_none": brain.artifact_store.at_time(
            "answer:refunds",
            scope=TENANT_B,
            known_at=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
        )
        is None,
    }

    evidence_ref_scope_dropped, evidence_ref_keys_collide = (
        _document_evidence_ref_scope_check()
    )

    isolation_holds = all(
        (
            document_id_collision["same_id_in_both_tenants"],
            document_id_collision["bodies_differ"],
            document_id_collision["refs_distinct"],
            scoped_store["cross_scope_lookup_is_none"],
            scoped_store["tenant_b_ref_never_resolves_in_a"],
            scoped_store["unknown_scope_ref_is_none"],
            scoped_store["identical_revision_kept_per_tenant"],
            restricted_refund_hidden_from_contractor,
            every_hit_in_user_tenant,
            evidence["scoped_evidence_accepted"],
            evidence["cross_tenant_evidence_rejected"],
            artifacts["tenant_b_get_is_none"],
            artifacts["tenant_b_history_is_empty"],
            artifacts["tenant_b_at_time_is_none"],
        )
    )

    return {
        "space": SPACE,
        "tenants": [scope.tenant for scope in scopes],
        "document_id_collision": document_id_collision,
        "scoped_store": scoped_store,
        "authorization": authorization,
        "retrieval": {
            "query": QUERY,
            "hits": retrieval,
            "every_hit_in_user_tenant": every_hit_in_user_tenant,
            "restricted_refund_hidden_from_contractor": (
                restricted_refund_hidden_from_contractor
            ),
        },
        "vector_index": {
            "unscoped_identical_ids_collapse": unscoped_collapse["ids_indexed"]
            < unscoped_collapse["ids_before"],
            "ids_before": unscoped_collapse["ids_before"],
            "ids_indexed_unscoped": unscoped_collapse["ids_indexed"],
            "tenant_qualified_hits_for_alice": vector_hits,
            "all_vector_hits_are_tenant_a": all(
                hit.startswith("tenant-a::") for hit in vector_hits
            ),
        },
        "evidence_boundary": evidence,
        "artifact_store": artifacts,
        "host_responsibility_hazards": {
            "index_trusts_host_allowed_refs": host_supplied_refs_are_trusted,
            "missing_visible_refs_admits_cross_tenant_evidence": (
                unguarded_report.accepted
            ),
            "parse_answer_collapses_identical_document_ids": parser_collapse,
            "document_evidence_ref_drops_scope": evidence_ref_scope_dropped,
            "document_evidence_ref_keys_collide_across_tenants": (
                evidence_ref_keys_collide
            ),
        },
        "isolation_holds": isolation_holds,
    }


def _tiny_vector(document: KnowledgeDocument) -> np.ndarray:
    """Deterministic stand-in for a caller embedding; refunds point at axis 0."""

    if "refund" in f"{document.title} {document.body}".casefold():
        return np.asarray([[1.0, 0.0, 0.0]], np.float32)
    return np.asarray([[0.0, 1.0, 0.0]], np.float32)


def _document_evidence_ref_scope_check() -> tuple[bool, bool]:
    # Same document_id and revision in two tenants; the adapter has no scope to
    # keep them apart, so the resulting ArtifactRef keys are identical.
    left = document_evidence_ref(
        Evidence(document_id=REFUNDS_A.document_id, revision="shared-1")
    )
    right = document_evidence_ref(
        Evidence(document_id=REFUNDS_B.document_id, revision="shared-1")
    )
    return left.ref.scope is None, left.ref.key == right.ref.key


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
