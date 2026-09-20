"""Durability review audit for the SQLite company-brain store.

Owned by the wave-2 durability reviewer. These tests target serialization and
transaction design: metadata/datetime/ACL roundtrips, source binding, failed
batches, independent connections, and tenant-separated duplicate IDs. Process
crash durability (``os._exit`` failpoints) belongs to the crash tester and is
deliberately not duplicated here.

Every assertion follows the Wave 2 shared contract for
``examples/company_brains/durable/store.py``; a failure means the builder's
implementation diverges from the agreed durable API.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

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
from mari_kit.json import to_json_value
from mari_kit.sync import SyncPlan, plan_sync

SOURCE_ID = "kb:acme"
OTHER_SOURCE_ID = "kb:other"
SCOPE = ScopeRef(tenant="acme", space="handbook")
OTHER_TENANT = ScopeRef(tenant="beta", space="handbook")


def document(
    external_id: str,
    body: str,
    revision: str,
    *,
    source_id: str = SOURCE_ID,
    title: str | None = None,
    updated_at: str = "",
    metadata: dict[str, object] | None = None,
    visibility: str = "connector_scope",
    principals: tuple[Principal, ...] = (),
    provider_revision: str = "",
    source_url: str = "",
) -> KnowledgeDocument:
    return KnowledgeDocument(
        source_id=source_id,
        external_id=external_id,
        title=title if title is not None else external_id.replace("/", " ").title(),
        body=body,
        revision=revision,
        provider_revision=provider_revision,
        updated_at=updated_at,
        source_url=source_url,
        acl=DocumentACL(visibility=visibility, principals=principals),
        metadata={} if metadata is None else metadata,
    )


def full_plan(
    state: object,
    documents: tuple[KnowledgeDocument, ...],
    *,
    source_id: str = SOURCE_ID,
    cursor: str = "cursor:full:done",
    configuration_fingerprint: str = "",
) -> SyncPlan:
    return plan_sync(
        state,
        PollPage(upserts=documents, next_cursor=cursor, snapshot_complete=True),
        source_id=source_id,
        mode=SyncMode.FULL,
        configuration_fingerprint=configuration_fingerprint,
    )


def incremental_plan(
    state: object,
    *,
    source_id: str = SOURCE_ID,
    upserts: tuple[KnowledgeDocument, ...] = (),
    tombstones: tuple[Tombstone, ...] = (),
    cursor: str = "cursor:inc:1",
    configuration_fingerprint: str = "",
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
        configuration_fingerprint=configuration_fingerprint,
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


def test_metadata_datetime_and_acl_roundtrip_across_reopen(tmp_path: Path) -> None:
    path = str(tmp_path)
    observation = document(
        "policy/security",
        "Security incidents page the on-call engineer.",
        "r1",
        title="Security Policy",
        updated_at="2024-03-01T12:30:00+02:00",
        metadata={
            "nested": {"tags": ["finance", "eu"], "count": 3, "enabled": True},
            "owner": "café ☕",
            "ratio": 1.5,
            "missing": None,
        },
        visibility="restricted",
        principals=(
            Principal(kind="group", identifier="security"),
            Principal(kind="user", identifier="alice"),
        ),
        provider_revision="provider-42",
        source_url="https://example.test/policy/security",
    )
    assert observation.updated_at == "2024-03-01T10:30:00Z"

    with SQLiteBrainStore(path) as store:
        sync_full(store, (observation,))

    with SQLiteBrainStore(path) as reopened:
        loaded = reopened.get_document(SCOPE, observation.document_id)
        assert loaded == observation
        assert loaded is not None
        assert loaded.acl.visibility == "restricted"
        assert set(loaded.acl.principals) == {
            Principal(kind="group", identifier="security"),
            Principal(kind="user", identifier="alice"),
        }
        assert loaded.updated_at == "2024-03-01T10:30:00Z"
        assert to_json_value(loaded.metadata) == {
            "nested": {"tags": ["finance", "eu"], "count": 3, "enabled": True},
            "owner": "café ☕",
            "ratio": 1.5,
            "missing": None,
        }
        assert loaded.provider_revision == "provider-42"
        assert loaded.source_url == "https://example.test/policy/security"
        assert reopened.projection(SCOPE) == {observation.document_id: observation.body}


def test_sync_state_all_fields_roundtrip_including_manifest_and_active_mode(
    tmp_path: Path,
) -> None:
    path = str(tmp_path)
    first = document("policy/access", "Access needs approval.", "r1")
    second = document("policy/payroll", "Payroll closes monthly.", "r1")

    with SQLiteBrainStore(path) as store:
        initial = store.state(SCOPE, SOURCE_ID)
        assert initial == store.state(SCOPE, SOURCE_ID)
        assert initial.source_id == "" and initial.generation == 0
        plan = incremental_plan(
            initial,
            upserts=(first,),
            configuration_fingerprint="connector:acme:v1",
        )
        store.apply_plan(SCOPE, plan)
        planned_state = plan.state

    with SQLiteBrainStore(path) as reopened:
        loaded = reopened.state(SCOPE, SOURCE_ID)
        assert loaded == planned_state
        assert loaded.generation == 1
        assert loaded.active_mode is None
        assert loaded.full_seen == frozenset()
        assert loaded.cursor == "cursor:inc:1"
        assert loaded.configuration_fingerprint == "connector:acme:v1"
        assert set(loaded.manifest) == {first.document_id}
        entry = loaded.manifest[first.document_id]
        assert entry.source_id == SOURCE_ID
        assert entry.external_id == "policy/access"
        assert entry.revision == "r1"
        assert entry.fingerprint

        incomplete = plan_sync(
            loaded,
            PollPage(
                upserts=(second,),
                next_checkpoint="cursor:full:1",
                snapshot_complete=False,
            ),
            source_id=SOURCE_ID,
            mode=SyncMode.FULL,
            configuration_fingerprint="connector:acme:v1",
        )
        reopened.apply_plan(SCOPE, incomplete)

    with SQLiteBrainStore(path) as reopened:
        loaded = reopened.state(SCOPE, SOURCE_ID)
        assert loaded == incomplete.state
        assert loaded.active_mode is SyncMode.FULL
        assert loaded.checkpoint == "cursor:full:1"
        assert loaded.full_seen == frozenset({second.document_id})
        assert set(loaded.manifest) == {first.document_id, second.document_id}
        assert loaded.generation == 2


def test_source_binding_rejects_foreign_upserts_and_tombstones_before_writes(
    tmp_path: Path,
) -> None:
    path = str(tmp_path)
    local = document("policy/access", "Access needs approval.", "r1")

    with SQLiteBrainStore(path) as store:
        sync_full(store, (local,))
        before_state = store.state(SCOPE, SOURCE_ID)
        before_docs = store.documents(SCOPE)
        before_projection = store.projection(SCOPE)

        foreign = document(
            "policy/access",
            "Foreign body.",
            "r9",
            source_id=OTHER_SOURCE_ID,
        )
        foreign_upsert = SyncPlan(
            upserts=(foreign,),
            deletes=(),
            unchanged=(),
            state=before_state,
            snapshot_complete=True,
            expected_generation=before_state.generation,
        )
        with pytest.raises(ValueError):
            store.apply_plan(SCOPE, foreign_upsert)

        foreign_delete = SyncPlan(
            upserts=(),
            deletes=(
                Tombstone(source_id=OTHER_SOURCE_ID, external_id="policy/access"),
            ),
            unchanged=(),
            state=before_state,
            snapshot_complete=True,
            expected_generation=before_state.generation,
        )
        with pytest.raises(ValueError):
            store.apply_plan(SCOPE, foreign_delete)

        assert store.state(SCOPE, SOURCE_ID) == before_state
        assert store.documents(SCOPE) == before_docs
        assert store.projection(SCOPE) == before_projection
        assert store.get_document(SCOPE, foreign.document_id) is None


def test_distinct_sources_share_a_scope_with_independent_state(
    tmp_path: Path,
) -> None:
    path = str(tmp_path)
    acme = document("policy/access", "Acme access.", "r1")
    other = document(
        "policy/access",
        "Other access.",
        "r1",
        source_id=OTHER_SOURCE_ID,
    )

    with SQLiteBrainStore(path) as store:
        sync_full(store, (acme,), source_id=SOURCE_ID)
        sync_full(store, (other,), source_id=OTHER_SOURCE_ID)
        assert store.state(SCOPE, SOURCE_ID).generation == 1
        assert store.state(SCOPE, OTHER_SOURCE_ID).generation == 1

        acme_next = document("policy/travel", "Acme travel.", "r1")
        store.apply_plan(
            SCOPE,
            incremental_plan(
                store.state(SCOPE, SOURCE_ID),
                source_id=SOURCE_ID,
                upserts=(acme_next,),
            ),
        )

        assert store.state(SCOPE, SOURCE_ID).generation == 2
        assert store.state(SCOPE, OTHER_SOURCE_ID).generation == 1
        assert store.get_document(SCOPE, acme.document_id) == acme
        assert store.get_document(SCOPE, other.document_id) == other
        assert store.projection(SCOPE) == {
            acme.document_id: acme.body,
            other.document_id: other.body,
            acme_next.document_id: acme_next.body,
        }


def test_generation_mismatch_is_rejected_without_any_write(tmp_path: Path) -> None:
    path = str(tmp_path)
    first = document("policy/access", "Access needs approval.", "r1")

    with SQLiteBrainStore(path) as store:
        plan = full_plan(store.state(SCOPE, SOURCE_ID), (first,))
        store.apply_plan(SCOPE, plan)
        after_state = store.state(SCOPE, SOURCE_ID)
        after_docs = store.documents(SCOPE)
        after_projection = store.projection(SCOPE)

        with pytest.raises(ValueError, match="generation"):
            store.apply_plan(SCOPE, plan)

        assert store.state(SCOPE, SOURCE_ID) == after_state
        assert store.documents(SCOPE) == after_docs
        assert store.projection(SCOPE) == after_projection


def test_concurrent_plans_from_one_generation_cannot_both_commit(
    tmp_path: Path,
) -> None:
    path = str(tmp_path)
    winner = document("policy/refunds", "Refunds within thirty days.", "r1")
    loser = document("policy/travel", "Travel needs pre-approval.", "r1")

    with SQLiteBrainStore(path) as store_a, SQLiteBrainStore(path) as store_b:
        state = store_a.state(SCOPE, SOURCE_ID)
        plan_a = full_plan(state, (winner,))
        plan_b = full_plan(state, (loser,))
        assert plan_a.expected_generation == plan_b.expected_generation == 0

        store_a.apply_plan(SCOPE, plan_a)

        with pytest.raises(ValueError, match="generation"):
            store_b.apply_plan(SCOPE, plan_b)

        assert store_b.state(SCOPE, SOURCE_ID).generation == 1
        ids = {item.document_id for item in store_b.documents(SCOPE)}
        assert winner.document_id in ids
        assert loser.document_id not in ids
        assert loser.document_id not in store_b.projection(SCOPE)


@pytest.mark.parametrize(
    "failing_stage", ["after_documents", "after_projection", "before_commit"]
)
def test_failed_batch_rolls_back_documents_projection_and_state(
    tmp_path: Path, failing_stage: str
) -> None:
    path = str(tmp_path)
    base = document("policy/access", "Access needs approval.", "r1")

    with SQLiteBrainStore(path) as store:
        sync_full(store, (base,))
        before_state = store.state(SCOPE, SOURCE_ID)
        before_docs = store.documents(SCOPE)
        before_projection = store.projection(SCOPE)

        edited = document("policy/access", "Access now needs two approvals.", "r2")
        added = document("policy/travel", "Travel needs pre-approval.", "r1")
        plan = incremental_plan(before_state, upserts=(edited, added))

        def failpoint(stage: str) -> None:
            if stage == failing_stage:
                raise RuntimeError(f"injected failure at {stage}")

        with pytest.raises(RuntimeError, match=failing_stage):
            store.apply_plan(SCOPE, plan, failpoint=failpoint)

        assert store.state(SCOPE, SOURCE_ID) == before_state
        assert store.documents(SCOPE) == before_docs
        assert store.projection(SCOPE) == before_projection

        fresh = SQLiteBrainStore(path)
        try:
            assert fresh.state(SCOPE, SOURCE_ID) == before_state
            assert fresh.documents(SCOPE) == before_docs
            assert fresh.projection(SCOPE) == before_projection
        finally:
            fresh.close()

        store.apply_plan(SCOPE, plan)
        assert store.state(SCOPE, SOURCE_ID) == plan.state
        assert store.get_document(SCOPE, added.document_id) == added
        assert store.get_document(SCOPE, edited.document_id) == edited


def test_failpoint_stages_are_named_and_ordered(tmp_path: Path) -> None:
    path = str(tmp_path)
    stages: list[str] = []

    with SQLiteBrainStore(path) as store:
        plan = full_plan(
            store.state(SCOPE, SOURCE_ID),
            (document("policy/access", "Access needs approval.", "r1"),),
        )
        store.apply_plan(SCOPE, plan, failpoint=stages.append)

    assert stages == [
        "after_documents",
        "after_projection",
        "before_commit",
        "after_commit",
    ]


def test_after_commit_failure_does_not_undo_committed_data(tmp_path: Path) -> None:
    path = str(tmp_path)
    base = document("policy/access", "Access needs approval.", "r1")

    with SQLiteBrainStore(path) as store:
        plan = full_plan(store.state(SCOPE, SOURCE_ID), (base,))

        def failpoint(stage: str) -> None:
            if stage == "after_commit":
                raise RuntimeError("observer failed after commit")

        with pytest.raises(RuntimeError, match="after commit"):
            store.apply_plan(SCOPE, plan, failpoint=failpoint)

        assert store.state(SCOPE, SOURCE_ID) == plan.state
        assert store.get_document(SCOPE, base.document_id) == base
        assert store.projection(SCOPE) == {base.document_id: base.body}


def test_independent_connections_read_freshly_committed_state(tmp_path: Path) -> None:
    path = str(tmp_path)
    first = document("policy/access", "Access needs approval.", "r1")
    second = document("policy/travel", "Travel needs pre-approval.", "r1")

    writer = SQLiteBrainStore(path)
    try:
        sync_full(writer, (first,))
        reader = SQLiteBrainStore(path)
        try:
            assert reader.state(SCOPE, SOURCE_ID) == writer.state(SCOPE, SOURCE_ID)
            assert reader.documents(SCOPE) == writer.documents(SCOPE)

            plan = incremental_plan(writer.state(SCOPE, SOURCE_ID), upserts=(second,))
            writer.apply_plan(SCOPE, plan)

            assert reader.state(SCOPE, SOURCE_ID) == plan.state
            assert {item.document_id for item in reader.documents(SCOPE)} == {
                first.document_id,
                second.document_id,
            }
            assert reader.projection(SCOPE)[second.document_id] == second.body
        finally:
            reader.close()
    finally:
        writer.close()


def test_tenant_separated_same_ids_are_isolated(tmp_path: Path) -> None:
    path = str(tmp_path)
    acme = document("policy/access", "Acme access policy.", "r1")
    beta = document("policy/access", "Beta access policy.", "r2")
    assert acme.document_id == beta.document_id

    with SQLiteBrainStore(path) as store:
        sync_full(store, (acme,), scope=SCOPE)
        sync_full(store, (beta,), scope=OTHER_TENANT)
        store.set_groups(SCOPE, "u1", {"acme_group"})
        store.set_groups(OTHER_TENANT, "u1", {"beta_group"})
        store.save_cache(SCOPE, "answer", {"tenant": "acme"})
        store.save_cache(OTHER_TENANT, "answer", {"tenant": "beta"})

    with SQLiteBrainStore(path) as reopened:
        assert reopened.get_document(SCOPE, acme.document_id) == acme
        assert reopened.get_document(OTHER_TENANT, beta.document_id) == beta
        assert reopened.projection(SCOPE) == {acme.document_id: acme.body}
        assert reopened.projection(OTHER_TENANT) == {beta.document_id: beta.body}
        assert reopened.state(SCOPE, SOURCE_ID).generation == 1
        assert reopened.state(OTHER_TENANT, SOURCE_ID).generation == 1
        assert reopened.groups(SCOPE, "u1") == frozenset({"acme_group"})
        assert reopened.groups(OTHER_TENANT, "u1") == frozenset({"beta_group"})
        assert reopened.load_cache(SCOPE, "answer") == {"tenant": "acme"}
        assert reopened.load_cache(OTHER_TENANT, "answer") == {"tenant": "beta"}


def test_same_revision_acl_and_metadata_observation_updates_live_document(
    tmp_path: Path,
) -> None:
    path = str(tmp_path)
    original = document(
        "policy/security",
        "Security incidents page the on-call engineer.",
        "r1",
        metadata={"classification": "internal"},
    )

    with SQLiteBrainStore(path) as store:
        sync_full(store, (original,))
        observation = document(
            "policy/security",
            original.body,
            original.revision,
            metadata={"classification": "confidential", "reviewed": True},
            visibility="restricted",
            principals=(Principal(kind="group", identifier="security"),),
        )
        plan = incremental_plan(store.state(SCOPE, SOURCE_ID), upserts=(observation,))
        assert [item.document_id for item in plan.upserts] == [original.document_id]

        store.apply_plan(SCOPE, plan)

        live = store.get_document(SCOPE, original.document_id)
        assert live is not None
        assert live.revision == original.revision
        assert live.body == original.body
        assert live.acl.visibility == "restricted"
        assert live.acl.principals == (Principal(kind="group", identifier="security"),)
        assert dict(live.metadata) == {
            "classification": "confidential",
            "reviewed": True,
        }
        assert store.projection(SCOPE) == {original.document_id: original.body}
        assert store.state(SCOPE, SOURCE_ID).generation == 2


def test_projection_tracks_edits_and_removals(tmp_path: Path) -> None:
    path = str(tmp_path)
    base = document("policy/access", "Access needs approval.", "r1")

    with SQLiteBrainStore(path) as store:
        sync_full(store, (base,))
        edited = document("policy/access", "Access needs two approvals.", "r2")
        store.apply_plan(
            SCOPE,
            incremental_plan(store.state(SCOPE, SOURCE_ID), upserts=(edited,)),
        )
        assert store.projection(SCOPE) == {edited.document_id: edited.body}
        assert store.get_document(SCOPE, base.document_id) == edited

        store.apply_plan(
            SCOPE,
            incremental_plan(
                store.state(SCOPE, SOURCE_ID),
                tombstones=(
                    Tombstone(source_id=SOURCE_ID, external_id="policy/access"),
                ),
            ),
        )
        assert store.projection(SCOPE) == {}
        assert store.documents(SCOPE) == ()
        assert store.get_document(SCOPE, base.document_id) is None


def test_groups_and_access_snapshot_are_durable_and_consistent(
    tmp_path: Path,
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
        assert store.groups(SCOPE, "unknown") == frozenset()
        store.set_groups(SCOPE, "alice", {"security", "managers"})
        store.set_groups(SCOPE, "alice", {"security"})
        documents, groups = store.access_snapshot(SCOPE, "alice")
        assert documents == store.documents(SCOPE)
        assert groups == frozenset({"security"})
        assert store.access_snapshot(SCOPE, "bob") == (
            store.documents(SCOPE),
            frozenset(),
        )

    with SQLiteBrainStore(path) as reopened:
        assert reopened.groups(SCOPE, "alice") == frozenset({"security"})
        assert reopened.groups(SCOPE, "bob") == frozenset()


def test_cache_roundtrip_preserves_json_nested_payload_and_normalizes_times(
    tmp_path: Path,
) -> None:
    path = str(tmp_path)
    payload = {
        "answer": "Refunds within thirty days.",
        "evidence": [{"id": "kb:acme/policy/refunds", "start": 0, "end": 4}],
        "flags": {"cached": True, "hits": 2, "score": 0.5, "missing": None},
    }

    with SQLiteBrainStore(path) as store:
        assert store.load_cache(SCOPE, "missing") is None
        store.save_cache(SCOPE, "q:refunds", payload)
        assert store.load_cache(SCOPE, "q:refunds") == payload

        store.save_cache(
            SCOPE,
            "q:when",
            {"observed": dt.datetime(2024, 3, 1, 10, 30, tzinfo=dt.UTC)},
        )

    with SQLiteBrainStore(path) as reopened:
        assert reopened.load_cache(SCOPE, "q:refunds") == payload
        assert reopened.load_cache(SCOPE, "q:when") == {
            "observed": "2024-03-01T10:30:00Z"
        }
        assert reopened.load_cache(OTHER_TENANT, "q:refunds") is None


def test_canonical_document_ids_are_used_in_projection_keys(tmp_path: Path) -> None:
    path = str(tmp_path)
    nested = document("team/eng/policy/access", "Access needs approval.", "r1")

    with SQLiteBrainStore(path) as store:
        sync_full(store, (nested,))
        expected = canonical_document_id(SOURCE_ID, "team/eng/policy/access")
        assert nested.document_id == expected
        assert set(store.projection(SCOPE)) == {expected}
        assert store.get_document(SCOPE, expected) == nested
