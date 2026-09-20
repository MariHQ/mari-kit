from __future__ import annotations

import datetime as dt
import json

import numpy as np
import pytest

from examples.company_brains import isolation as brain
from mari_kit import Evidence, KnowledgeDocument, Principal
from mari_kit.knowledge import (
    assess_freshness,
    document_evidence_ref,
    validate_located_evidence,
)
from mari_kit.platform import (
    InMemoryArtifactStore,
    InMemoryDocumentStore,
    RevisionConflict,
)
from mari_kit.references import LocatedEvidence, RevisionRef, ScopeRef
from mari_kit.retrieval import build_index, search_index
from mari_kit.testing import (
    assert_artifact_store_conforms,
    assert_authorizer_conforms,
    assert_document_store_conforms,
    assert_index_authorization_conforms,
)


def test_run_output_is_json_serializable_and_reports_isolated():
    result = brain.run()
    json.dumps(result)
    assert result["document_id_collision"]["same_id_in_both_tenants"] is True
    assert result["document_id_collision"]["bodies_differ"] is True
    assert result["isolation_holds"] is True
    assert result["retrieval"]["every_hit_in_user_tenant"] is True
    assert result["evidence_boundary"]["cross_tenant_evidence_rejected"] is True


def test_identical_document_ids_stay_distinct_in_scoped_store():
    assert brain.REFUNDS_A.document_id == brain.REFUNDS_B.document_id
    store = InMemoryDocumentStore()
    store.commit(brain.REFUNDS_A, scope=brain.TENANT_A, expected_revision=None)
    store.commit(brain.REFUNDS_B, scope=brain.TENANT_B, expected_revision=None)
    assert (
        store.get(brain.SHARED_SOURCE, brain.REFUND_EXTERNAL, scope=brain.TENANT_A).body
        == brain.REFUNDS_A.body
    )
    assert (
        store.get(brain.SHARED_SOURCE, brain.REFUND_EXTERNAL, scope=brain.TENANT_B).body
        == brain.REFUNDS_B.body
    )
    assert (
        store.get(
            brain.SHARED_SOURCE,
            brain.REFUND_EXTERNAL,
            scope=ScopeRef(tenant="tenant-c", space=brain.SPACE),
        )
        is None
    )


def test_cross_scope_resolution_requires_matching_scope():
    brain_instance = brain.CompanyBrain()
    store = brain_instance.document_store
    assert store.resolve(brain.REFUNDS_A.ref_in(brain.TENANT_A)) == brain.REFUNDS_A
    assert store.resolve(brain.REFUNDS_B.ref_in(brain.TENANT_B)) == brain.REFUNDS_B
    # A tenant-b revision addressed inside tenant-a must not fall through.
    assert store.resolve(brain.REFUNDS_B.ref_in(brain.TENANT_A)) is None
    with pytest.raises(ValueError, match="scoped reference"):
        store.resolve(brain.REFUNDS_A.ref)


def test_store_rejects_stale_and_duplicate_revisions():
    store = InMemoryDocumentStore()
    store.commit(brain.REFUNDS_A, scope=brain.TENANT_A, expected_revision=None)
    next_revision = KnowledgeDocument(
        source_id=brain.SHARED_SOURCE,
        external_id=brain.REFUND_EXTERNAL,
        title="Refund policy",
        body="Tenant A enterprise refunds are issued within 45 days.",
        revision="a-refunds-2",
    )
    with pytest.raises(RevisionConflict):
        store.commit(next_revision, scope=brain.TENANT_A, expected_revision=None)
    with pytest.raises(ValueError, match="already exists"):
        store.commit(
            brain.REFUNDS_A, scope=brain.TENANT_A, expected_revision="a-refunds-1"
        )


def test_reference_stores_pass_public_conformance_checks():
    assert_document_store_conforms(InMemoryDocumentStore)
    assert_artifact_store_conforms(InMemoryArtifactStore)


def test_artifact_store_isolates_identical_artifact_ids_across_tenants():
    first = brain.CompanyBrain().commit_answer(
        brain.ALICE,
        "tenant-a answer",
        (
            LocatedEvidence(
                ref=brain.REFUNDS_A.ref_in(brain.TENANT_A), quote=brain.REFUNDS_A.body
            ),
        ),
    )
    second = brain.CompanyBrain().commit_answer(
        brain.BOB,
        "tenant-b answer",
        (
            LocatedEvidence(
                ref=brain.REFUNDS_B.ref_in(brain.TENANT_B), quote=brain.REFUNDS_B.body
            ),
        ),
    )
    assert first.artifact_id == second.artifact_id == "answer:refunds"
    isolated = InMemoryArtifactStore()
    isolated.commit(first, expected_revision=None)
    isolated.commit(second, expected_revision=None)
    assert isolated.get("answer:refunds", scope=brain.TENANT_A).value["answer"] == (
        "tenant-a answer"
    )
    assert isolated.get("answer:refunds", scope=brain.TENANT_B).value["answer"] == (
        "tenant-b answer"
    )
    assert isolated.get("answer:refunds", scope=ScopeRef(tenant="tenant-c")) is None


def test_per_user_authorization_combines_tenant_wall_and_acl():
    brain_instance = brain.CompanyBrain()
    alice_docs = brain_instance.authorized_documents(brain.ALICE)
    carol_docs = brain_instance.authorized_documents(brain.CAROL)
    bob_docs = brain_instance.authorized_documents(brain.BOB)
    assert brain.REFUNDS_A in alice_docs and brain.STATUS_A in alice_docs
    assert carol_docs == (brain.STATUS_A,)
    assert brain.REFUNDS_B in bob_docs and brain.STATUS_B in bob_docs
    for docs, user in ((alice_docs, brain.ALICE), (carol_docs, brain.CAROL)):
        assert all(document in brain.DOCUMENTS[user.tenant] for document in docs)


def test_tenant_authorizer_conforms_and_denies_cross_tenant():
    alice_authorizer = brain.TenantAuthorizer(brain.ALICE)
    assert_authorizer_conforms(
        alice_authorizer,
        principal=brain.ALICE.principals,
        allowed_ref=brain.REFUNDS_A.ref_in(brain.TENANT_A).object,
        denied_ref=brain.REFUNDS_B.ref_in(brain.TENANT_B).object,
    )
    # The tenant wall is checked before ACL metadata, even for an unknown scope.
    assert not alice_authorizer(
        brain.ALICE.principals,
        brain.REFUNDS_B.ref_in(ScopeRef(tenant="tenant-c", space=brain.SPACE)).object,
    )
    carol_authorizer = brain.TenantAuthorizer(brain.CAROL)
    assert carol_authorizer(
        brain.CAROL.principals, brain.STATUS_A.ref_in(brain.TENANT_A).object
    )
    assert not carol_authorizer(
        brain.CAROL.principals, brain.REFUNDS_A.ref_in(brain.TENANT_A).object
    )


def test_scoped_retrieval_filters_before_ranking():
    brain_instance = brain.CompanyBrain()
    alice_hits = brain_instance.search(brain.ALICE, brain.QUERY)
    carol_hits = brain_instance.search(brain.CAROL, brain.QUERY)
    bob_hits = brain_instance.search(brain.BOB, brain.QUERY)
    assert alice_hits[0].ref == brain.REFUNDS_A.ref_in(brain.TENANT_A)
    assert {hit.ref.object.scope.tenant for hit in alice_hits} == {"tenant-a"}
    assert {hit.ref.object.scope.tenant for hit in bob_hits} == {"tenant-b"}
    assert {hit.ref for hit in carol_hits} == {brain.STATUS_A.ref_in(brain.TENANT_A)}
    assert all(hit.ref != brain.REFUNDS_A.ref_in(brain.TENANT_A) for hit in bob_hits)
    assert_index_authorization_conforms(
        brain_instance.index,
        query=brain.QUERY,
        allowed_ref=brain.STATUS_A.ref_in(brain.TENANT_A),
        hit_ref=lambda hit: hit.ref,
    )


def test_index_applies_host_supplied_allowed_refs_verbatim():
    brain_instance = brain.CompanyBrain()
    both = brain_instance.authorized_refs(brain.ALICE) | brain_instance.authorized_refs(
        brain.BOB
    )
    hits = brain_instance.index.search(brain.QUERY, limit=10, allowed_refs=both)
    assert {hit.ref for hit in hits} == both
    assert brain_instance.index.search(brain.QUERY, limit=10, allowed_refs=set()) == ()


def test_scoped_evidence_accepts_only_visible_refs():
    brain_instance = brain.CompanyBrain()
    safe = (
        LocatedEvidence(
            ref=brain.REFUNDS_A.ref_in(brain.TENANT_A), quote=brain.REFUNDS_A.body
        ),
    )
    accepted = validate_located_evidence(
        safe,
        resolve_material=brain_instance.resolve_body,
        visible_refs=brain_instance.authorized_refs(brain.ALICE),
    )
    assert accepted.accepted
    cross = (
        LocatedEvidence(
            ref=brain.REFUNDS_B.ref_in(brain.TENANT_B), quote=brain.REFUNDS_B.body
        ),
    )
    rejected = validate_located_evidence(
        cross,
        resolve_material=brain_instance.resolve_body,
        visible_refs=brain_instance.authorized_refs(brain.ALICE),
    )
    assert not rejected.accepted
    assert {issue.kind.value for issue in rejected.issues} == {"not_visible"}


def test_missing_visible_refs_admits_cross_tenant_evidence():
    # Failure path owned by the host: omitting visible_refs makes the validator
    # trust any resolvable reference, so callers must always pass the
    # authorized scoped set.
    brain_instance = brain.CompanyBrain()
    cross = (
        LocatedEvidence(
            ref=brain.REFUNDS_B.ref_in(brain.TENANT_B), quote=brain.REFUNDS_B.body
        ),
    )
    unguarded = validate_located_evidence(
        cross, resolve_material=brain_instance.resolve_body, visible_refs=None
    )
    assert unguarded.accepted


def test_parse_answer_rejects_conflicting_identical_document_ids():
    assert brain.REFUNDS_A.document_id == brain.REFUNDS_B.document_id
    assert brain._accepts_evidence((brain.REFUNDS_A, brain.REFUNDS_B)) is False
    assert brain._accepts_evidence((brain.REFUNDS_B, brain.REFUNDS_A)) is False


def test_document_evidence_ref_drops_scope():
    # Legacy unscoped evidence cannot infer a tenant; scope must be supplied.
    left = document_evidence_ref(
        Evidence(document_id=brain.REFUNDS_A.document_id, revision="shared-1")
    )
    right = document_evidence_ref(
        Evidence(document_id=brain.REFUNDS_B.document_id, revision="shared-1")
    )
    assert left.ref.scope is None
    assert left.ref.key == right.ref.key


def test_document_evidence_adapter_retains_explicit_scope():
    evidence = Evidence(document_id=brain.REFUNDS_A.document_id, revision="shared-1")
    left = document_evidence_ref(evidence, scope=brain.TENANT_A)
    right = document_evidence_ref(evidence, scope=brain.TENANT_B)
    assert left.ref.scope == brain.TENANT_A
    assert right.ref.scope == brain.TENANT_B
    assert left.ref.key != right.ref.key


def test_evidence_freshness_dependencies_are_not_tenant_scoped():
    # Regression probe for a core API gap: Evidence and KnowledgeDependency key
    # by bare document_id, so a caller's current_revisions map can describe only
    # one tenant when two tenants share a document_id. The scoped alternative is
    # assess_revision_refs with RevisionRef/ObjectRef scopes.
    report = assess_freshness(
        brain._alice_answer().evidence,
        {brain.REFUNDS_A.document_id: brain.REFUNDS_B.revision},
    )
    assert report.status.value == "stale"
    assert report.changes[0].current_revision == brain.REFUNDS_B.revision


def test_unscoped_vector_index_collapses_identical_document_ids():
    unscoped = {
        document.document_id: np.asarray([[1.0, 0.0]], np.float32)
        for documents in brain.DOCUMENTS.values()
        for document in documents
    }
    assert len(unscoped) == 2
    unscoped_index = build_index(unscoped)
    assert len(unscoped_index.document_ids) == 2
    qualified = {
        f"{tenant}::{document.document_id}": np.asarray(
            [[1.0, 0.0] if "refund" in document.body else [0.0, 1.0]], np.float32
        )
        for tenant, documents in brain.DOCUMENTS.items()
        for document in documents
    }
    qualified_index = build_index(qualified)
    assert len(qualified_index.document_ids) == 4
    hits = search_index(
        qualified_index,
        np.asarray([[1.0, 0.0]], np.float32),
        limit=10,
        allowed_document_ids={"tenant-a::confluence:acme/page:refunds"},
    )
    assert [hit.document_id for hit in hits] == [
        "tenant-a::confluence:acme/page:refunds"
    ]


def test_cross_tenant_revision_ref_carries_scope_in_its_key():
    left = brain.REFUNDS_A.ref_in(brain.TENANT_A)
    right = brain.REFUNDS_B.ref_in(brain.TENANT_B)
    assert isinstance(left, RevisionRef)
    assert left.key != right.key
    assert left.object.scope == brain.TENANT_A
    assert right.object.scope == brain.TENANT_B


def test_artifact_at_time_is_scoped():
    store = InMemoryArtifactStore()
    artifact = brain.CompanyBrain().commit_answer(
        brain.ALICE,
        "tenant-a answer",
        (
            LocatedEvidence(
                ref=brain.REFUNDS_A.ref_in(brain.TENANT_A), quote=brain.REFUNDS_A.body
            ),
        ),
    )
    store.commit(artifact, expected_revision=None)
    known_at = dt.datetime(2025, 1, 1, tzinfo=dt.UTC)
    assert (
        store.at_time("answer:refunds", scope=brain.TENANT_A, known_at=known_at)
        == artifact
    )
    assert (
        store.at_time("answer:refunds", scope=brain.TENANT_B, known_at=known_at) is None
    )


def test_scope_rejects_blank_tenant():
    with pytest.raises(ValueError, match="tenant and space"):
        ScopeRef(tenant="  ", space=brain.SPACE)


def test_principal_is_required_for_restricted_documents():
    with pytest.raises(ValueError, match="principal kind and identifier"):
        Principal(kind="", identifier="finance")
