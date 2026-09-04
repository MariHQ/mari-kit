"""Reusable conformance checks for artifact-store adapters."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable

from mari_components.knowledge.artifacts import (
    Activity,
    KnowledgeArtifact,
    KnowledgeScope,
)
from mari_components.platform.stores import (
    ArtifactStore,
    DocumentStore,
    RevisionConflict,
)
from mari_components.references import ObjectRef, RevisionRef, ScopeRef
from mari_components.types import KnowledgeDocument


def assert_artifact_store_conforms(factory: Callable[[], ArtifactStore]) -> None:
    """Check isolation, CAS, history, and recorded-time semantics."""

    store = factory()
    assert store.capabilities.compare_and_swap
    assert store.capabilities.point_in_time_reads
    assert store.capabilities.history
    assert store.capabilities.scope_isolation
    first_scope = KnowledgeScope(tenant="tenant-a", space="space-a")
    other_space = KnowledgeScope(tenant="tenant-a", space="space-b")
    other_tenant = KnowledgeScope(tenant="tenant-b", space="space-a")
    activity = Activity(identifier="conformance", implementation="test")
    later_recorded = dt.datetime(2026, 2, 1, tzinfo=dt.UTC)
    earlier_recorded = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    first = KnowledgeArtifact(
        artifact_id="policy",
        revision="v1",
        value="first",
        scope=first_scope,
        recorded_at=later_recorded,
        generated_by=activity,
    )
    second = KnowledgeArtifact(
        artifact_id="policy",
        revision="v2",
        value="second",
        scope=first_scope,
        recorded_at=earlier_recorded,
        generated_by=activity,
        supersedes=("policy@v1",),
    )
    store.commit(first, expected_revision=None)
    store.commit(second, expected_revision="v1")
    assert store.get("policy", scope=first_scope) == second
    assert store.get("policy", scope=other_space) is None
    assert store.get("policy", scope=other_tenant) is None
    assert store.history("policy", scope=first_scope) == (first, second)
    assert (
        store.at_time(
            "policy",
            scope=first_scope,
            known_at=dt.datetime(2026, 1, 15, tzinfo=dt.UTC),
        )
        == second
    )
    try:
        store.commit(second, expected_revision="v1")
    except RevisionConflict:
        pass
    else:
        raise AssertionError("store did not enforce compare-and-swap")


def assert_document_store_conforms(factory: Callable[[], DocumentStore]) -> None:
    """Check document identity, revision lookup, CAS, and scope isolation."""

    store = factory()
    scope = ScopeRef(tenant="tenant-a", space="space-a")
    other_space = ScopeRef(tenant="tenant-a", space="space-b")
    first = KnowledgeDocument(
        source_id="github:acme/docs",
        external_id="file:policy.md",
        title="Policy",
        body="Thirty days",
        revision="v1",
    )
    second = KnowledgeDocument(
        source_id=first.source_id,
        external_id=first.external_id,
        title=first.title,
        body="Fourteen days",
        revision="v2",
    )
    store.commit(first, scope=scope, expected_revision=None)
    store.commit(second, scope=scope, expected_revision="v1")
    assert store.get(first.source_id, first.external_id, scope=scope) == second
    assert store.get(first.source_id, first.external_id, scope=other_space) is None
    assert store.history(first.source_id, first.external_id, scope=scope) == (
        first,
        second,
    )
    ref = RevisionRef(
        object=ObjectRef(
            namespace=first.source_id,
            object_id=first.external_id,
            scope=scope,
        ),
        revision="v1",
    )
    assert store.resolve(ref) == first
