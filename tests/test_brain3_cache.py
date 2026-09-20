"""Wave-3 cache tests for the durable company brain fast path.

These tests pin the new cheap-token caching contract without changing any
observable answer semantics:

* the store exposes monotonic document/membership epochs and a consistent
  ``access_token_snapshot`` read;
* a ``CompanyBrain`` memoizes the authorized snapshot and BM25 index under that
  token, so an unchanged request avoids full document reads and index rebuilds;
* a durable edit, delete, same-revision ACL change, or group change advances the
  token and invalidates the memoized view, including when the change arrives
  through a second SQLite connection;
* a store that only implements the legacy ``access_snapshot`` API still works.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from examples.company_brains.durable import engine as engine_module
from examples.company_brains.durable.engine import CompanyBrain
from examples.company_brains.durable.store import SQLiteBrainStore
from mari_kit import (
    DocumentACL,
    KnowledgeDocument,
    PollPage,
    Principal,
    ScopeRef,
    SyncMode,
    Tombstone,
)
from mari_kit.retrieval import RevisionBM25Index
from mari_kit.sync import plan_sync

SOURCE = "handbook:wave3"
SCOPE = ScopeRef(tenant="wave3", space="brain")
SUPPORT = Principal(kind="team", identifier="support")
QUESTION = "What is the refund window?"
OTHER_QUESTION = "When is orientation?"
QUERY = "refund window"


def document(
    external_id: str,
    body: str,
    revision: str,
    *,
    title: str,
    visibility: str = "restricted",
    principals: tuple[Principal, ...] = (SUPPORT,),
) -> KnowledgeDocument:
    return KnowledgeDocument(
        source_id=SOURCE,
        external_id=external_id,
        title=title,
        body=body,
        revision=revision,
        acl=DocumentACL(visibility=visibility, principals=principals),
    )


POLICY = document(
    "refunds", "The refund window is 30 days.", "v1", title="Refund policy"
)
PUBLIC = document(
    "orientation",
    "New employees attend orientation on Monday.",
    "v1",
    title="Onboarding",
    visibility="public",
)


def sync_full(store: SQLiteBrainStore, *documents: KnowledgeDocument) -> None:
    plan = plan_sync(
        store.state(SCOPE, SOURCE),
        PollPage(upserts=tuple(documents), snapshot_complete=True),
        source_id=SOURCE,
        mode=SyncMode.FULL,
    )
    store.apply_plan(SCOPE, plan)


def sync_incremental(
    store: SQLiteBrainStore,
    *,
    upserts: tuple[KnowledgeDocument, ...] = (),
    tombstones: tuple[Tombstone, ...] = (),
) -> None:
    plan = plan_sync(
        store.state(SCOPE, SOURCE),
        PollPage(upserts=upserts, tombstones=tombstones, snapshot_complete=True),
        source_id=SOURCE,
        mode=SyncMode.INCREMENTAL,
    )
    store.apply_plan(SCOPE, plan)


class CountingStore(SQLiteBrainStore):
    """A store that records how often the engine touched full document rows."""

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self.token_reads = 0
        self.snapshot_reads = 0
        self.legacy_reads = 0

    def access_token(self, scope: ScopeRef, user_id: str):  # type: ignore[no-untyped-def]
        self.token_reads += 1
        return super().access_token(scope, user_id)

    def access_token_snapshot(self, scope: ScopeRef, user_id: str):  # type: ignore[no-untyped-def]
        self.snapshot_reads += 1
        return super().access_token_snapshot(scope, user_id)

    def access_snapshot(self, scope: ScopeRef, user_id: str):  # type: ignore[no-untyped-def]
        self.legacy_reads += 1
        return super().access_snapshot(scope, user_id)


class _CountingIndex(RevisionBM25Index):
    builds = 0

    def __init__(self, *args: object, **kwargs: object) -> None:
        type(self).builds += 1
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]


@pytest.fixture
def path(tmp_path: object) -> str:
    return str(tmp_path)


def test_access_token_is_cheap_consistent_and_monotonic(path: str) -> None:
    with SQLiteBrainStore(path) as store:
        sync_full(store, PUBLIC, POLICY)
        before = store.access_token(SCOPE, "alice")
        assert before == store.access_token(SCOPE, "alice")

        token, documents, groups = store.access_token_snapshot(SCOPE, "alice")
        assert token == before
        assert documents == store.documents(SCOPE)
        assert groups == store.groups(SCOPE, "alice")
        assert store.access_snapshot(SCOPE, "alice") == (documents, groups)

        # A state-only synchronization that observes no change must not advance
        # the token, so callers can keep their memoized snapshots.
        sync_incremental(store, upserts=(PUBLIC, POLICY))
        assert store.access_token(SCOPE, "alice") == before

        store.set_groups(SCOPE, "alice", {"support"})
        granted = store.access_token(SCOPE, "alice")
        assert granted != before
        store.set_groups(SCOPE, "alice", {"support"})
        assert store.access_token(SCOPE, "alice") == granted

        sync_incremental(
            store,
            upserts=(
                replace(
                    POLICY,
                    body="The refund window is 45 days.",
                    revision="v2",
                    content_digest="",
                ),
            ),
        )
        assert store.access_token(SCOPE, "alice") != granted


def test_repeat_search_avoids_reloading_documents(path: str) -> None:
    store = CountingStore(path)
    try:
        sync_full(store, PUBLIC, POLICY)
        store.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(store, SCOPE)

        assert brain.search(QUERY, user_id="alice") == (POLICY,)
        assert store.snapshot_reads == 1

        assert brain.search(QUERY, user_id="alice") == (POLICY,)
        assert store.snapshot_reads == 1
        assert store.token_reads >= 2

        sync_incremental(
            store,
            upserts=(
                replace(
                    POLICY,
                    body="The refund window is 45 days.",
                    revision="v2",
                    content_digest="",
                ),
            ),
        )
        refreshed = brain.search(QUERY, user_id="alice")
        assert store.snapshot_reads == 2
        assert refreshed[0].body == "The refund window is 45 days."
    finally:
        store.close()


def test_new_question_reuses_view_and_bm25_index(
    path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _CountingIndex.builds = 0
    monkeypatch.setattr(engine_module, "RevisionBM25Index", _CountingIndex)
    store = CountingStore(path)
    try:
        sync_full(store, PUBLIC, POLICY)
        store.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(store, SCOPE)

        first = brain.answer(QUESTION, user_id="alice")
        assert first["disposition"] == "grounded"
        assert store.snapshot_reads == 1
        assert _CountingIndex.builds == 1

        other = brain.answer(OTHER_QUESTION, user_id="alice")
        assert other["disposition"] == "grounded"
        assert store.snapshot_reads == 1
        assert _CountingIndex.builds == 1

        repeated = brain.answer(QUESTION, user_id="alice")
        assert repeated["cache_hit"] is True
        assert store.snapshot_reads == 1
        assert _CountingIndex.builds == 1
    finally:
        store.close()


def test_membership_change_invalidates_cached_answer_without_document_read(
    path: str,
) -> None:
    store = CountingStore(path)
    try:
        sync_full(store, PUBLIC, POLICY)
        store.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(store, SCOPE)

        warm = brain.answer(QUESTION, user_id="alice")
        assert warm["disposition"] == "grounded"
        assert store.snapshot_reads == 1

        store.set_groups(SCOPE, "alice", set())
        revoked = brain.answer(QUESTION, user_id="alice")

        assert revoked["disposition"] == "insufficient_evidence"
        assert revoked["cache_hit"] is False
        assert "30 days" not in revoked["answer"]
        assert store.snapshot_reads == 2
    finally:
        store.close()


def test_same_revision_acl_change_advances_token_and_revokes(path: str) -> None:
    with SQLiteBrainStore(path) as store:
        sync_full(store, PUBLIC, POLICY)
        store.set_groups(SCOPE, "alice", {"support"})
        store.set_groups(SCOPE, "bob", {"finance"})
        brain = CompanyBrain(store, SCOPE)
        token = store.access_token(SCOPE, "alice")
        assert brain.answer(QUESTION, user_id="alice")["disposition"] == "grounded"

        moved = replace(
            POLICY,
            content_digest="",
            acl=DocumentACL(
                visibility="restricted",
                principals=(Principal(kind="team", identifier="finance"),),
            ),
        )
        assert moved.revision == POLICY.revision
        sync_incremental(store, upserts=(moved,))
        assert store.access_token(SCOPE, "alice") != token

        revoked = brain.answer(QUESTION, user_id="alice")
        assert revoked["disposition"] == "insufficient_evidence"
        assert revoked["cache_hit"] is False

        granted = brain.answer(QUESTION, user_id="bob")
        assert granted["disposition"] == "grounded"
        assert "30 days" in granted["answer"]


def test_title_only_edit_advances_document_epoch(path: str) -> None:
    with SQLiteBrainStore(path) as store:
        sync_full(store, PUBLIC)
        brain = CompanyBrain(store, SCOPE)
        before = store.access_token(SCOPE, "alice")
        assert brain.search(QUERY, user_id="alice") == ()

        retitled = replace(PUBLIC, title="Refund policy", content_digest="")
        sync_incremental(store, upserts=(retitled,))
        assert store.access_token(SCOPE, "alice") != before
        assert brain.search(QUERY, user_id="alice") == (retitled,)


def test_second_connection_edit_and_revocation_invalidate_view(path: str) -> None:
    writer = SQLiteBrainStore(path)
    reader = CountingStore(path)
    try:
        sync_full(writer, PUBLIC, POLICY)
        writer.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(reader, SCOPE)

        first = brain.answer(QUESTION, user_id="alice")
        assert first["disposition"] == "grounded"
        assert reader.snapshot_reads == 1

        writer.set_groups(SCOPE, "alice", set())
        revoked = brain.answer(QUESTION, user_id="alice")
        assert revoked["disposition"] == "insufficient_evidence"
        assert revoked["cache_hit"] is False
        assert reader.snapshot_reads == 2

        sync_full(
            writer,
            replace(POLICY, body="The refund window is 45 days.", content_digest=""),
        )
        writer.set_groups(SCOPE, "alice", {"support"})
        edited = brain.answer(QUESTION, user_id="alice")
        assert "45 days" in edited["answer"]
        assert edited["cache_hit"] is False
        assert reader.snapshot_reads == 3
    finally:
        reader.close()
        writer.close()


def test_callback_race_is_not_served_from_memoized_view(path: str) -> None:
    writer = SQLiteBrainStore(path)
    reader = SQLiteBrainStore(path)
    try:
        sync_full(writer, PUBLIC)
        brain = CompanyBrain(reader, SCOPE)
        old_quote = PUBLIC.body

        def racing(question: str, documents: tuple[KnowledgeDocument, ...]) -> dict:
            sync_full(
                writer,
                replace(
                    PUBLIC, body="Orientation moved to Tuesday.", content_digest=""
                ),
            )
            return {
                "answer": old_quote,
                "disposition": "grounded",
                "evidence": [{"document_id": PUBLIC.document_id, "quote": old_quote}],
            }

        result = brain.answer(OTHER_QUESTION, user_id="alice", generate=racing)
        assert "Monday" not in result["answer"]
        stored = reader.get_document(SCOPE, PUBLIC.document_id)
        assert stored is not None and "Tuesday" in stored.body
    finally:
        reader.close()
        writer.close()


def test_deletion_invalidates_memoized_view(path: str) -> None:
    store = CountingStore(path)
    try:
        sync_full(store, PUBLIC, POLICY)
        store.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(store, SCOPE)
        assert brain.answer(QUESTION, user_id="alice")["disposition"] == "grounded"
        assert store.snapshot_reads == 1

        sync_incremental(
            store,
            tombstones=(Tombstone(source_id=SOURCE, external_id="refunds"),),
        )
        after = brain.answer(QUESTION, user_id="alice")
        assert after["disposition"] == "insufficient_evidence"
        assert store.snapshot_reads == 2
        assert brain.search(QUERY, user_id="alice") == ()
    finally:
        store.close()


def test_view_cache_is_bounded_per_brain(path: str) -> None:
    with SQLiteBrainStore(path) as store:
        sync_full(store, PUBLIC, POLICY)
        store.set_groups(SCOPE, "alice", {"support"})
        store.set_groups(SCOPE, "bob", set())
        brain = CompanyBrain(store, SCOPE, view_cache_size=1)

        assert brain.search(QUERY, user_id="alice") == (POLICY,)
        assert brain.search(QUERY, user_id="bob") == ()
        assert brain.search(QUERY, user_id="alice") == (POLICY,)
        assert len(brain._views) <= 1


def test_legacy_store_without_tokens_still_works(path: str) -> None:
    with SQLiteBrainStore(path) as store:
        sync_full(store, PUBLIC, POLICY)
        store.set_groups(SCOPE, "alice", {"support"})
        store.access_token = None  # type: ignore[method-assign]
        store.access_token_snapshot = None  # type: ignore[method-assign]
        brain = CompanyBrain(store, SCOPE)

        assert brain.search(QUERY, user_id="alice") == (POLICY,)
        warm = brain.answer(QUESTION, user_id="alice")
        assert warm["disposition"] == "grounded"
        assert brain.answer(QUESTION, user_id="alice")["cache_hit"] is True

        store.set_groups(SCOPE, "alice", set())
        revoked = brain.answer(QUESTION, user_id="alice")
        assert revoked["disposition"] == "insufficient_evidence"
        assert revoked["cache_hit"] is False
        assert "30 days" not in revoked["answer"]
