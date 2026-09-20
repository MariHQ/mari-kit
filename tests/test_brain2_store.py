"""Direct smoke tests for the durable SQLite company-brain store.

These are the durability builder's compact behavioral checks. They focus on
persistence across reopen, source/scope isolation, same-revision ACL
observations, consistent access snapshots, and real atomicity: a child process
killed with ``os._exit`` at each failpoint stage must leave no partial plan,
while a kill after commit must be durable.
"""

from __future__ import annotations

import os

import pytest

from examples.company_brains.durable.store import SQLiteBrainStore
from mari_kit import (
    DocumentACL,
    KnowledgeDocument,
    PollPage,
    Principal,
    ScopeRef,
    SyncMode,
    Tombstone,
    canonical_document_id,
)
from mari_kit.sync import SyncPlan, plan_sync

SOURCE_ID = "kb:acme"
OTHER_SOURCE_ID = "kb:other"
SCOPE = ScopeRef(tenant="acme", space="handbook")
OTHER_SCOPE = ScopeRef(tenant="acme", space="policies")
OTHER_TENANT = ScopeRef(tenant="beta", space="handbook")


def document(
    external_id: str,
    body: str,
    revision: str,
    *,
    source_id: str = SOURCE_ID,
    metadata: dict[str, object] | None = None,
    visibility: str = "connector_scope",
    principals: tuple[Principal, ...] = (),
) -> KnowledgeDocument:
    return KnowledgeDocument(
        source_id=source_id,
        external_id=external_id,
        title=external_id.replace("/", " ").title(),
        body=body,
        revision=revision,
        acl=DocumentACL(visibility=visibility, principals=principals),
        metadata={} if metadata is None else metadata,
    )


def full_plan(
    state: object,
    documents: tuple[KnowledgeDocument, ...],
    *,
    source_id: str = SOURCE_ID,
    cursor: str = "cursor:full:done",
) -> SyncPlan:
    return plan_sync(
        state,
        PollPage(upserts=documents, next_cursor=cursor, snapshot_complete=True),
        source_id=source_id,
        mode=SyncMode.FULL,
    )


def incremental_plan(
    state: object,
    *,
    source_id: str = SOURCE_ID,
    upserts: tuple[KnowledgeDocument, ...] = (),
    tombstones: tuple[Tombstone, ...] = (),
    cursor: str = "cursor:inc:1",
) -> SyncPlan:
    return plan_sync(
        state,
        PollPage(
            upserts=upserts,
            tombstones=tombstones,
            next_cursor=cursor,
            snapshot_complete=True,
        ),
        source_id=source_id,
        mode=SyncMode.INCREMENTAL,
    )


def sync_full(
    store: SQLiteBrainStore,
    documents: tuple[KnowledgeDocument, ...],
    *,
    scope: ScopeRef = SCOPE,
    source_id: str = SOURCE_ID,
) -> SyncPlan:
    plan = full_plan(store.state(scope, source_id), documents, source_id=source_id)
    store.apply_plan(scope, plan)
    return plan


def test_persists_documents_projection_state_cache_and_groups_across_reopen(
    tmp_path: object,
) -> None:
    path = str(tmp_path)
    access = document("policy/access", "Access needs approval.", "r1")
    nested = document("team/eng/policy/travel", "Travel needs pre-approval.", "r1")

    with SQLiteBrainStore(path) as store:
        plan = sync_full(store, (access, nested))
        store.set_groups(SCOPE, "alice", {"security", "managers"})
        store.set_groups(SCOPE, "alice", {"security"})
        store.save_cache(SCOPE, "q:access", {"answer": "manager", "hits": 2})

    with SQLiteBrainStore(path) as reopened:
        assert reopened.documents(SCOPE) == (access, nested)
        assert reopened.state(SCOPE, SOURCE_ID) == plan.state
        assert reopened.projection(SCOPE) == {
            access.document_id: access.body,
            nested.document_id: nested.body,
        }
        assert reopened.groups(SCOPE, "alice") == frozenset({"security"})
        assert reopened.load_cache(SCOPE, "q:access") == {
            "answer": "manager",
            "hits": 2,
        }
        assert reopened.get_document(SCOPE, nested.document_id) == nested
        assert canonical_document_id(SOURCE_ID, "team/eng/policy/travel") == (
            nested.document_id
        )


def test_state_and_documents_are_isolated_by_scope_and_source(tmp_path: object) -> None:
    path = str(tmp_path)
    acme = document("policy/access", "Acme access.", "r1")
    beta = document("policy/access", "Beta access.", "r2")
    other = document("policy/access", "Other source.", "r1", source_id=OTHER_SOURCE_ID)

    with SQLiteBrainStore(path) as store:
        sync_full(store, (acme,), scope=SCOPE)
        sync_full(store, (beta,), scope=OTHER_TENANT)
        sync_full(store, (other,), scope=SCOPE, source_id=OTHER_SOURCE_ID)

        assert store.get_document(SCOPE, acme.document_id) == acme
        assert store.get_document(OTHER_TENANT, beta.document_id) == beta
        assert store.get_document(SCOPE, other.document_id) == other
        assert store.get_document(OTHER_SCOPE, acme.document_id) is None
        assert store.state(SCOPE, SOURCE_ID).generation == 1
        assert store.state(SCOPE, OTHER_SOURCE_ID).generation == 1
        assert store.state(OTHER_TENANT, SOURCE_ID).generation == 1

        store.set_groups(SCOPE, "u1", {"a"})
        store.set_groups(OTHER_TENANT, "u1", {"b"})
        assert store.groups(SCOPE, "u1") == frozenset({"a"})
        assert store.groups(OTHER_TENANT, "u1") == frozenset({"b"})


def test_reject_foreign_source_and_generation_mismatch_without_writes(
    tmp_path: object,
) -> None:
    path = str(tmp_path)
    base = document("policy/access", "Access needs approval.", "r1")

    with SQLiteBrainStore(path) as store:
        sync_full(store, (base,))
        before_state = store.state(SCOPE, SOURCE_ID)
        before_documents = store.documents(SCOPE)
        before_projection = store.projection(SCOPE)

        foreign = SyncPlan(
            upserts=(
                document("policy/access", "Foreign.", "r9", source_id=OTHER_SOURCE_ID),
            ),
            deletes=(),
            unchanged=(),
            state=before_state,
            snapshot_complete=True,
            expected_generation=before_state.generation,
        )
        with pytest.raises(ValueError, match="foreign"):
            store.apply_plan(SCOPE, foreign)
        assert store.state(SCOPE, SOURCE_ID) == before_state
        assert store.documents(SCOPE) == before_documents
        assert store.projection(SCOPE) == before_projection

        stale = full_plan(before_state, (base,))
        store.apply_plan(SCOPE, stale)
        with pytest.raises(ValueError, match="generation"):
            store.apply_plan(SCOPE, stale)

        assert store.state(SCOPE, SOURCE_ID) == stale.state
        assert store.documents(SCOPE) == before_documents


def test_same_revision_acl_observation_updates_live_document(tmp_path: object) -> None:
    path = str(tmp_path)
    original = document(
        "policy/security",
        "Security incidents page on-call.",
        "r1",
        metadata={"classification": "internal"},
    )
    observed = document(
        "policy/security",
        original.body,
        "r1",
        metadata={"classification": "confidential"},
        visibility="restricted",
        principals=(Principal(kind="group", identifier="security"),),
    )

    with SQLiteBrainStore(path) as store:
        sync_full(store, (original,))
        plan = incremental_plan(store.state(SCOPE, SOURCE_ID), upserts=(observed,))
        assert [item.document_id for item in plan.upserts] == [original.document_id]
        store.apply_plan(SCOPE, plan)

        live = store.get_document(SCOPE, original.document_id)
        assert live is not None
        assert live.revision == "r1"
        assert live.body == original.body
        assert live.acl.visibility == "restricted"
        assert live.acl.principals == (Principal(kind="group", identifier="security"),)
        assert dict(live.metadata) == {"classification": "confidential"}
        assert store.projection(SCOPE) == {original.document_id: original.body}
        assert store.state(SCOPE, SOURCE_ID).generation == 2


def test_access_snapshot_reads_documents_and_groups_consistently(
    tmp_path: object,
) -> None:
    path = str(tmp_path)
    docs = (
        document("policy/access", "Access needs approval.", "r1"),
        document(
            "policy/security",
            "Security incidents page on-call.",
            "r1",
            visibility="restricted",
            principals=(Principal(kind="group", identifier="security"),),
        ),
    )

    with SQLiteBrainStore(path) as store:
        sync_full(store, docs)
        store.set_groups(SCOPE, "alice", {"security", "managers"})
        assert store.access_snapshot(SCOPE, "alice") == (
            store.documents(SCOPE),
            frozenset({"security", "managers"}),
        )
        assert store.access_snapshot(SCOPE, "bob") == (
            store.documents(SCOPE),
            frozenset(),
        )


def _crash_at(path: str, scope: ScopeRef, plan: SyncPlan, stage: str) -> None:
    pid = os.fork()
    if pid == 0:
        try:
            with SQLiteBrainStore(path) as store:

                def failpoint(name: str) -> None:
                    if name == stage:
                        os._exit(17)

                store.apply_plan(scope, plan, failpoint=failpoint)
        finally:
            os._exit(0)
    _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 17


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires posix fork")
@pytest.mark.parametrize(
    "stage", ["after_documents", "after_projection", "before_commit"]
)
def test_crash_before_commit_rolls_back_the_whole_plan(
    tmp_path: object, stage: str
) -> None:
    path = str(tmp_path)
    base = document("policy/access", "Access needs approval.", "r1")

    with SQLiteBrainStore(path) as store:
        sync_full(store, (base,))
        before_state = store.state(SCOPE, SOURCE_ID)
        before_documents = store.documents(SCOPE)
        before_projection = store.projection(SCOPE)
        plan = incremental_plan(
            before_state,
            upserts=(
                document("policy/access", "Access needs two approvals.", "r2"),
                document("policy/travel", "Travel needs pre-approval.", "r1"),
            ),
        )

        _crash_at(path, SCOPE, plan, stage)

        with SQLiteBrainStore(path) as fresh:
            assert fresh.state(SCOPE, SOURCE_ID) == before_state
            assert fresh.documents(SCOPE) == before_documents
            assert fresh.projection(SCOPE) == before_projection

        store.apply_plan(SCOPE, plan)
        assert store.state(SCOPE, SOURCE_ID) == plan.state


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires posix fork")
def test_crash_after_commit_is_durable(tmp_path: object) -> None:
    path = str(tmp_path)
    base = document("policy/access", "Access needs approval.", "r1")

    with SQLiteBrainStore(path) as store:
        sync_full(store, (base,))
        edited = document("policy/access", "Access needs two approvals.", "r2")
        plan = incremental_plan(store.state(SCOPE, SOURCE_ID), upserts=(edited,))

        _crash_at(path, SCOPE, plan, "after_commit")

        with SQLiteBrainStore(path) as fresh:
            assert fresh.state(SCOPE, SOURCE_ID) == plan.state
            assert fresh.get_document(SCOPE, edited.document_id) == edited
            assert fresh.projection(SCOPE) == {edited.document_id: edited.body}


def test_tombstone_removes_document_and_projection(tmp_path: object) -> None:
    path = str(tmp_path)
    base = document("policy/access", "Access needs approval.", "r1")

    with SQLiteBrainStore(path) as store:
        sync_full(store, (base,))
        store.apply_plan(
            SCOPE,
            incremental_plan(
                store.state(SCOPE, SOURCE_ID),
                tombstones=(
                    Tombstone(source_id=SOURCE_ID, external_id="policy/access"),
                ),
            ),
        )
        assert store.documents(SCOPE) == ()
        assert store.projection(SCOPE) == {}
        assert store.get_document(SCOPE, base.document_id) is None
