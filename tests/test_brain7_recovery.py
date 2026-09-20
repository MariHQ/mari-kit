"""Wave-7 recovery tests for the durable company brain.

These are the recovery agent's independent, deterministic integration checks of
how the host-owned SQLite brain comes back after a restart or an interrupted
write.  They deliberately cross the boundaries that the store- and engine-level
suites exercise in isolation:

* a paginated authoritative full snapshot is persisted one page at a time and
  the store is closed and reopened after *every* page, with the reopened bytes
  compared against Mari Kit's pure planner rather than against the code under
  test;
* an incremental snapshot is interrupted mid-stream and the persisted
  ``cursor``/``checkpoint``/``active_mode`` drive the connector's next request;
* a partial full-snapshot lock survives a reopen and blocks an incremental
  resume (and the reverse);
* a child process is killed with ``os._exit`` at each failpoint of an
  incomplete page and the reopened store must roll the whole page back before
  the same page is re-applied;
* documents, source checkpoints, group memberships, and the two epoch counters
  stay isolated per scope/source/user across a reopen;
* the durable answer cache is a *shared* resource: a warm brain and a freshly
  reopened brain serve the same canonical record and invalidate it identically
  after a cross-connection edit, ACL change, membership change, or deletion.

Nothing here reaches the network, waits on wall-clock time, or needs more than
one interpreter beyond the ``fork`` crash cases (skipped when ``os.fork`` is
unavailable).
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

import pytest

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
    canonical_document_id,
)
from mari_kit.sync import SyncPlan, SyncState, plan_sync

SOURCE = "handbook"
OTHER_SOURCE = "release-notes"
SCOPE = ScopeRef(tenant="acme", space="handbook")
OTHER_TENANT = ScopeRef(tenant="beta", space="handbook")
OTHER_SPACE = ScopeRef(tenant="acme", space="policies")
SUPPORT = Principal(kind="team", identifier="support")
FINANCE = Principal(kind="team", identifier="finance")
QUESTION = "What is the refund window?"
QUOTE = "The refund window is 30 days."
STAGES = ("after_documents", "after_projection", "before_commit", "after_commit")


def document(
    external_id: str,
    body: str = QUOTE,
    revision: str = "r1",
    *,
    source_id: str = SOURCE,
    title: str | None = None,
    visibility: str = "restricted",
    principals: tuple[Principal, ...] = (SUPPORT,),
) -> KnowledgeDocument:
    return KnowledgeDocument(
        source_id=source_id,
        external_id=external_id,
        title=title or external_id.replace("/", " ").title(),
        body=body,
        revision=revision,
        acl=DocumentACL(visibility=visibility, principals=principals),
    )


def full_page(
    *upserts: KnowledgeDocument,
    cursor: str = "full:done",
    checkpoint: str | None = None,
    complete: bool = True,
) -> PollPage:
    return PollPage(
        upserts=tuple(upserts),
        next_cursor=cursor if complete else None,
        next_checkpoint=checkpoint,
        snapshot_complete=complete,
    )


def incremental_page(
    *upserts: KnowledgeDocument,
    tombstones: tuple[Tombstone, ...] = (),
    cursor: str = "inc:done",
    checkpoint: str | None = None,
    complete: bool = True,
) -> PollPage:
    return PollPage(
        upserts=tuple(upserts),
        tombstones=tombstones,
        next_cursor=cursor if complete else None,
        next_checkpoint=checkpoint,
        snapshot_complete=complete,
    )


def plan_for(
    store: SQLiteBrainStore,
    page: PollPage,
    mode: SyncMode,
    *,
    scope: ScopeRef = SCOPE,
    source_id: str = SOURCE,
) -> SyncPlan:
    return plan_sync(
        store.state(scope, source_id), page, source_id=source_id, mode=mode
    )


def apply_page(
    store: SQLiteBrainStore,
    page: PollPage,
    mode: SyncMode,
    *,
    scope: ScopeRef = SCOPE,
    source_id: str = SOURCE,
) -> SyncPlan:
    plan = plan_for(store, page, mode, scope=scope, source_id=source_id)
    store.apply_plan(scope, plan)
    return plan


def reduce_documents(
    documents: Iterable[KnowledgeDocument], plan: SyncPlan
) -> dict[str, KnowledgeDocument]:
    current = {item.document_id: item for item in documents}
    for item in plan.upserts:
        current[item.document_id] = item
    for tombstone in plan.deletes:
        current.pop(tombstone.document_id, None)
    return current


def stored_documents(
    store: SQLiteBrainStore, scope: ScopeRef = SCOPE
) -> dict[str, KnowledgeDocument]:
    return {item.document_id: item for item in store.documents(scope)}


def projection_of(documents: Iterable[KnowledgeDocument]) -> dict[str, str]:
    return {item.document_id: item.body for item in documents}


def sync_full(
    store: SQLiteBrainStore,
    *documents: KnowledgeDocument,
    scope: ScopeRef = SCOPE,
    source_id: str = SOURCE,
) -> SyncPlan:
    return apply_page(
        store,
        full_page(*documents),
        SyncMode.FULL,
        scope=scope,
        source_id=source_id,
    )


def sync_incremental(
    store: SQLiteBrainStore,
    *documents: KnowledgeDocument,
    tombstones: tuple[Tombstone, ...] = (),
    scope: ScopeRef = SCOPE,
    source_id: str = SOURCE,
) -> SyncPlan:
    return apply_page(
        store,
        incremental_page(*documents, tombstones=tombstones),
        SyncMode.INCREMENTAL,
        scope=scope,
        source_id=source_id,
    )


# --------------------------------------------------------------------------- #
# Partial/full checkpoint continuation across reopened stores
# --------------------------------------------------------------------------- #


FULL_PAGES = (
    full_page(
        document("policy/leave", "Leave is twenty days."),
        document("policy/refunds"),
        checkpoint="full:2",
        complete=False,
    ),
    full_page(
        document("policy/refunds"),  # resent unchanged on the second page
        document("policy/travel", "Travel requires approval.", visibility="public"),
        checkpoint="full:3",
        complete=False,
    ),
    full_page(document("policy/security", "Rotate secrets."), cursor="full:done"),
)


def _reference_full_pages() -> tuple[
    list[tuple[SyncState, dict[str, KnowledgeDocument]]], SyncState
]:
    state = SyncState()
    documents: dict[str, KnowledgeDocument] = {}
    expected: list[tuple[SyncState, dict[str, KnowledgeDocument]]] = []
    for page in FULL_PAGES:
        plan = plan_sync(state, page, source_id=SOURCE, mode=SyncMode.FULL)
        state = plan.state
        documents = reduce_documents(documents.values(), plan)
        expected.append((state, dict(documents)))
    return expected, state


def test_full_snapshot_checkpoint_continuation_survives_reopen(
    tmp_path: Path,
) -> None:
    """A paginated full snapshot is exactly recoverable after each page.

    The expected state after every page is produced by the pure planner, so the
    SQLite encode/decode path is never used to build its own oracle.
    """

    expected, final_state = _reference_full_pages()
    assert expected[0][0].active_mode is SyncMode.FULL
    assert expected[0][0].checkpoint == "full:2"
    assert expected[0][0].cursor is None
    assert expected[1][0].checkpoint == "full:3"
    assert expected[1][0].cursor is None
    assert expected[2][0].active_mode is None
    assert expected[2][0].checkpoint is None
    assert expected[2][0].cursor == "full:done"
    assert expected[2][0].full_seen == frozenset()

    path = tmp_path / "brain.sqlite"
    store = SQLiteBrainStore(path)
    try:
        for index, page in enumerate(FULL_PAGES):
            plan = plan_for(store, page, SyncMode.FULL)
            store.apply_plan(SCOPE, plan)

            expected_state, expected_documents = expected[index]
            assert store.state(SCOPE, SOURCE) == expected_state
            assert stored_documents(store) == expected_documents
            assert store.projection(SCOPE) == projection_of(expected_documents.values())

            # Reopen between every page: committed bytes alone must reconstruct
            # the planner's state, documents, and projection.
            store.close()
            store = SQLiteBrainStore(path)
            assert store.state(SCOPE, SOURCE) == expected_state
            assert stored_documents(store) == expected_documents
            assert store.projection(SCOPE) == projection_of(expected_documents.values())
    finally:
        store.close()

    with SQLiteBrainStore(path) as reopened:
        assert reopened.state(SCOPE, SOURCE) == final_state
        assert set(reopened.projection(SCOPE)) == set(stored_documents(reopened))


def test_partial_full_snapshot_reconciliation_after_reopen_deletes_absent(
    tmp_path: Path,
) -> None:
    path = tmp_path / "brain.sqlite"
    leave = document("policy/leave", "Leave is twenty days.")
    # A completed baseline owns the leave document.
    with SQLiteBrainStore(path) as store:
        sync_full(store, leave)

    # A *new* authoritative snapshot interrupts after its first page, and its
    # terminal page re-sends only the refund document.  Because leave was never
    # seen during this full run, the terminal page must reconcile it as absent.
    with SQLiteBrainStore(path) as store:
        apply_page(
            store,
            full_page(
                document("policy/refunds"),
                checkpoint="full:2",
                complete=False,
            ),
            SyncMode.FULL,
        )
        assert store.state(SCOPE, SOURCE).full_seen == frozenset(
            {document("policy/refunds").document_id}
        )

    with SQLiteBrainStore(path) as store:
        terminal = apply_page(
            store,
            full_page(document("policy/refunds"), cursor="full:done"),
            SyncMode.FULL,
        )

    assert [item.document_id for item in terminal.deletes] == [leave.document_id]
    assert terminal.deletes[0].reason == "absent_from_complete_snapshot"

    with SQLiteBrainStore(path) as reopened:
        assert stored_documents(reopened) == {
            document("policy/refunds").document_id: document("policy/refunds")
        }
        assert leave.document_id not in reopened.state(SCOPE, SOURCE).manifest


class CheckpointedSource:
    """A deterministic connector that resumes from the persisted checkpoint."""

    def __init__(self) -> None:
        self.requests: list[tuple[str | None, str | None]] = []

    def page(self, state: SyncState) -> PollPage:
        self.requests.append((state.cursor, state.checkpoint))
        if state.checkpoint == "inc:2":
            return incremental_page(
                document("policy/security", "Security incidents page on-call."),
                cursor="inc:done",
            )
        return incremental_page(
            document("policy/refunds"),
            checkpoint="inc:2",
            complete=False,
        )


def test_incremental_checkpoint_continuation_drives_source_after_reopen(
    tmp_path: Path,
) -> None:
    path = tmp_path / "brain.sqlite"
    with SQLiteBrainStore(path) as store:
        seeded = sync_full(store, document("policy/refunds"))
    assert seeded.state.cursor == "full:done"

    source = CheckpointedSource()

    with SQLiteBrainStore(path) as store:
        first = apply_page(
            store, source.page(store.state(SCOPE, SOURCE)), SyncMode.INCREMENTAL
        )
        assert first.snapshot_complete is False
        assert first.state.active_mode is SyncMode.INCREMENTAL
        # An incomplete page holds the durable cursor it had before.
        assert first.state.cursor == "full:done"
        assert first.state.checkpoint == "inc:2"
        assert first.state.generation == 2

    # Reopen and continue purely from the durable checkpoint.
    with SQLiteBrainStore(path) as store:
        resumed = store.state(SCOPE, SOURCE)
        assert resumed.checkpoint == "inc:2"
        assert resumed.active_mode is SyncMode.INCREMENTAL
        second = apply_page(store, source.page(resumed), SyncMode.INCREMENTAL)

    assert second.snapshot_complete is True
    assert second.state.active_mode is None
    assert second.state.cursor == "inc:done"
    assert second.state.checkpoint is None
    assert source.requests == [("full:done", None), ("full:done", "inc:2")]

    with SQLiteBrainStore(path) as reopened:
        assert reopened.state(SCOPE, SOURCE) == second.state
        assert set(stored_documents(reopened)) == {
            document("policy/refunds").document_id,
            document("policy/security", "Security incidents page on-call.").document_id,
        }


def test_partial_snapshot_mode_lock_survives_reopen(tmp_path: Path) -> None:
    path = tmp_path / "brain.sqlite"
    with SQLiteBrainStore(path) as store:
        apply_page(
            store,
            full_page(document("policy/refunds"), checkpoint="full:2", complete=False),
            SyncMode.FULL,
        )

    with SQLiteBrainStore(path) as store:
        assert store.state(SCOPE, SOURCE).active_mode is SyncMode.FULL
        with pytest.raises(ValueError, match="cannot resume"):
            plan_for(
                store,
                incremental_page(document("policy/travel")),
                SyncMode.INCREMENTAL,
            )

    with SQLiteBrainStore(path) as store:
        sync_full(store, document("policy/refunds"))
        apply_page(
            store,
            incremental_page(
                document("policy/refunds"), checkpoint="inc:2", complete=False
            ),
            SyncMode.INCREMENTAL,
        )

    with SQLiteBrainStore(path) as store:
        assert store.state(SCOPE, SOURCE).active_mode is SyncMode.INCREMENTAL
        with pytest.raises(ValueError, match="cannot resume"):
            plan_for(store, full_page(document("policy/travel")), SyncMode.FULL)


# --------------------------------------------------------------------------- #
# Process-death recovery of an incomplete page
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires posix fork")
@pytest.mark.parametrize("stage", STAGES)
def test_process_death_during_partial_page_then_resume(
    tmp_path: Path, stage: str
) -> None:
    path = tmp_path / "brain.sqlite"
    page = full_page(
        document("policy/refunds"),
        document("policy/travel"),
        checkpoint="full:2",
        complete=False,
    )

    with SQLiteBrainStore(path) as store:
        sync_full(store, document("policy/leave", "Leave is twenty days."))
        base_state = store.state(SCOPE, SOURCE)
        base_documents = stored_documents(store)
        base_projection = store.projection(SCOPE)
        base_token = store.access_token(SCOPE, "alice")
        plan = plan_for(store, page, SyncMode.FULL)

    pid = os.fork()
    if pid == 0:  # pragma: no cover - child always exits
        try:
            with SQLiteBrainStore(path) as store:

                def failpoint(name: str) -> None:
                    if name == stage:
                        os._exit(17)

                store.apply_plan(SCOPE, plan, failpoint=failpoint)
        finally:
            os._exit(0)
    _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 17

    with SQLiteBrainStore(path) as store:
        if stage == "after_commit":
            assert store.state(SCOPE, SOURCE) == plan.state
            assert stored_documents(store) == reduce_documents(
                base_documents.values(), plan
            )
            assert store.projection(SCOPE) == projection_of(
                stored_documents(store).values()
            )
            assert store.access_token(SCOPE, "alice").doc_epoch == (
                base_token.doc_epoch + 1
            )
            return

        # Pre-commit process death must leave the committed page untouched,
        # including the access counters (no phantom invalidation).
        assert store.state(SCOPE, SOURCE) == base_state
        assert stored_documents(store) == base_documents
        assert store.projection(SCOPE) == base_projection
        assert store.access_token(SCOPE, "alice") == base_token

        # The interrupted page can be re-planned from the recovered state.
        resumed = plan_for(store, page, SyncMode.FULL)
        assert resumed.state == plan.state
        store.apply_plan(SCOPE, resumed)
        assert store.state(SCOPE, SOURCE) == plan.state
        assert stored_documents(store) == reduce_documents(
            base_documents.values(), plan
        )
        assert store.projection(SCOPE) == projection_of(
            stored_documents(store).values()
        )


# --------------------------------------------------------------------------- #
# Scope, source, and user isolation across a reopen
# --------------------------------------------------------------------------- #


def test_reopened_store_isolates_scopes_sources_and_users(tmp_path: Path) -> None:
    path = tmp_path / "brain.sqlite"
    refunds = document("policy/refunds")
    note = document(
        "release/travel", "Travel requires approval.", source_id=OTHER_SOURCE
    )
    beta = document(
        "policy/refunds", "Beta refund window is 90 days.", source_id=OTHER_SOURCE
    )
    other_space = document("policy/refunds", "Other space refund is 60 days.")

    with SQLiteBrainStore(path) as store:
        sync_full(store, refunds)
        sync_full(store, beta, source_id=OTHER_SOURCE)
        sync_full(store, other_space, scope=OTHER_SPACE)
        store.set_groups(SCOPE, "alice", {"support"})
        store.set_groups(SCOPE, "bob", {"finance"})
        store.set_groups(OTHER_SPACE, "alice", {"finance"})
        # A partial full snapshot only owns its own source.
        apply_page(
            store,
            full_page(note, checkpoint="other:2", complete=False),
            SyncMode.FULL,
            source_id=OTHER_SOURCE,
        )
        before = {
            "state": store.state(SCOPE, SOURCE),
            "other_source": store.state(SCOPE, OTHER_SOURCE),
            "other_space": store.state(OTHER_SPACE, SOURCE),
            "token_alice": store.access_token(SCOPE, "alice"),
            "token_bob": store.access_token(SCOPE, "bob"),
            "token_other": store.access_token(OTHER_SPACE, "alice"),
        }

    with SQLiteBrainStore(path) as store:
        assert store.state(SCOPE, SOURCE) == before["state"]
        assert store.state(SCOPE, OTHER_SOURCE) == before["other_source"]
        assert store.state(OTHER_SPACE, SOURCE) == before["other_space"]
        assert store.access_token(SCOPE, "alice") == before["token_alice"]
        assert store.access_token(SCOPE, "bob") == before["token_bob"]
        assert store.access_token(OTHER_SPACE, "alice") == before["token_other"]

        assert set(stored_documents(store, SCOPE)) == {
            refunds.document_id,
            beta.document_id,
            note.document_id,
        }
        assert set(stored_documents(store, OTHER_SPACE)) == {other_space.document_id}
        assert store.groups(SCOPE, "alice") == frozenset({"support"})
        assert store.groups(SCOPE, "bob") == frozenset({"finance"})
        assert store.groups(OTHER_SPACE, "alice") == frozenset({"finance"})

        # The reopened partial lock belongs to exactly one source.
        assert store.state(SCOPE, OTHER_SOURCE).active_mode is SyncMode.FULL
        assert store.state(SCOPE, SOURCE).active_mode is None
        with pytest.raises(ValueError, match="cannot resume"):
            plan_for(
                store,
                incremental_page(document("policy/leave")),
                SyncMode.INCREMENTAL,
                source_id=OTHER_SOURCE,
            )

        brain = CompanyBrain(store, SCOPE)
        assert brain.answer(QUESTION, user_id="alice")["disposition"] == "grounded"
        assert brain.answer(QUESTION, user_id="bob")["disposition"] == (
            "insufficient_evidence"
        )


def test_document_and_membership_epochs_are_durable_and_idempotent(
    tmp_path: Path,
) -> None:
    path = tmp_path / "brain.sqlite"
    with SQLiteBrainStore(path) as store:
        sync_full(store, document("policy/refunds"))
        store.set_groups(SCOPE, "alice", {"support"})
        first = store.access_token(SCOPE, "alice")

    with SQLiteBrainStore(path) as store:
        assert store.access_token(SCOPE, "alice") == first
        # Re-setting the identical membership must not advance the epoch.
        store.set_groups(SCOPE, "alice", {"support"})
        assert store.access_token(SCOPE, "alice") == first

        # A document change advances only the document epoch.
        sync_incremental(
            store, document("policy/refunds", "The window is 45 days.", "r2")
        )
        after_edit = store.access_token(SCOPE, "alice")
        assert after_edit.doc_epoch == first.doc_epoch + 1
        assert after_edit.membership_epoch == first.membership_epoch

        # A membership change advances only the membership epoch.
        store.set_groups(SCOPE, "alice", {"support", "finance"})
        after_grant = store.access_token(SCOPE, "alice")
        assert after_grant.doc_epoch == after_edit.doc_epoch
        assert after_grant.membership_epoch == after_edit.membership_epoch + 1

    with SQLiteBrainStore(path) as reopened:
        assert reopened.access_token(SCOPE, "alice") == after_grant


# --------------------------------------------------------------------------- #
# Durable answer cache: fresh vs warm brains
# --------------------------------------------------------------------------- #


def test_durable_answer_cache_is_shared_by_fresh_and_restarted_brains(
    tmp_path: Path,
) -> None:
    path = tmp_path / "brain.sqlite"
    with SQLiteBrainStore(path) as store:
        sync_full(store, document("policy/refunds"))
        store.set_groups(SCOPE, "alice", {"support"})
        warm = CompanyBrain(store, SCOPE)
        generated = warm.answer(QUESTION, user_id="alice")
        assert generated["cache_hit"] is False
        assert QUOTE in generated["answer"]
        assert warm.answer(QUESTION, user_id="alice")["cache_hit"] is True

    # A brand-new interpreter state (new connection, new brain) reads the
    # persisted record and serves the identical prose without regenerating.
    with SQLiteBrainStore(path) as store:
        fresh = CompanyBrain(store, SCOPE)
        restarted = fresh.answer(QUESTION, user_id="alice")
        assert restarted["cache_hit"] is True
        assert restarted["answer"] == generated["answer"]
        assert restarted["evidence"] == generated["evidence"]

    # A second, concurrently open fresh brain is consistent as well.
    with SQLiteBrainStore(path) as store:
        second = CompanyBrain(store, SCOPE)
        assert second.answer(QUESTION, user_id="alice")["cache_hit"] is True


def test_durable_cache_invalidation_matches_fresh_and_warm_brains(
    tmp_path: Path,
) -> None:
    path = tmp_path / "brain.sqlite"
    writer = SQLiteBrainStore(path)
    reader = SQLiteBrainStore(path)
    try:
        sync_full(writer, document("policy/refunds"))
        writer.set_groups(SCOPE, "alice", {"support"})
        warm = CompanyBrain(reader, SCOPE)
        first = warm.answer(QUESTION, user_id="alice")
        assert first["cache_hit"] is False
        assert QUOTE in first["answer"]

        # A cross-connection body edit invalidates the persisted record.  The
        # fresh brain answers first and regenerates the new prose; the warm
        # brain must then reuse that record, never the stale "30 days" one.
        sync_incremental(
            writer, document("policy/refunds", "The refund window is 45 days.", "r2")
        )

        with SQLiteBrainStore(path) as fresh_store:
            fresh = CompanyBrain(fresh_store, SCOPE)
            fresh_after = fresh.answer(QUESTION, user_id="alice")
            warm_after = warm.answer(QUESTION, user_id="alice")
            assert fresh_after["cache_hit"] is False
            assert "45 days" in fresh_after["answer"]
            assert warm_after["cache_hit"] is True
            assert "30 days" not in warm_after["answer"]
            assert warm_after["answer"] == fresh_after["answer"]

            # A membership revocation is observed identically by both brains
            # even though the warm brain answers first this time.
            writer.set_groups(SCOPE, "alice", set())
            warm_revoked = warm.answer(QUESTION, user_id="alice")
            fresh_revoked = fresh.answer(QUESTION, user_id="alice")
            assert warm_revoked["disposition"] == "insufficient_evidence"
            assert fresh_revoked["disposition"] == "insufficient_evidence"
            assert "45 days" not in warm_revoked["answer"]
            assert warm_revoked["answer"] == fresh_revoked["answer"]
    finally:
        reader.close()
        writer.close()


def test_deleted_document_invalidates_restarted_cache(tmp_path: Path) -> None:
    path = tmp_path / "brain.sqlite"
    with SQLiteBrainStore(path) as store:
        sync_full(store, document("policy/refunds"))
        store.set_groups(SCOPE, "alice", {"support"})
        CompanyBrain(store, SCOPE).answer(QUESTION, user_id="alice")

    with SQLiteBrainStore(path) as store:
        sync_incremental(
            store,
            tombstones=(Tombstone(source_id=SOURCE, external_id="policy/refunds"),),
        )

    with SQLiteBrainStore(path) as reopened:
        answer = CompanyBrain(reopened, SCOPE).answer(QUESTION, user_id="alice")
        assert answer["cache_hit"] is False
        assert answer["disposition"] == "insufficient_evidence"
        assert QUOTE not in answer["answer"]
        assert (
            reopened.get_document(
                SCOPE, canonical_document_id(SOURCE, "policy/refunds")
            )
            is None
        )


def test_same_revision_acl_change_invalidates_warm_and_fresh_after_reopen(
    tmp_path: Path,
) -> None:
    """A same-revision ACL move survives a restart and is not silently served.

    The provider revision is unchanged, so only the ACL observation changes;
    the durable digest covers it and both a warm reader and a freshly opened
    brain must stop serving the old grounded prose.
    """

    path = tmp_path / "brain.sqlite"
    writer = SQLiteBrainStore(path)
    reader = SQLiteBrainStore(path)
    try:
        sync_full(writer, document("policy/refunds"))
        writer.set_groups(SCOPE, "alice", {"support"})
        warm = CompanyBrain(reader, SCOPE)
        assert warm.answer(QUESTION, user_id="alice")["disposition"] == "grounded"

        # Same revision "r1", same body, restricted to a different team.
        writer_after = document("policy/refunds", QUOTE, "r1", principals=(FINANCE,))
        sync_incremental(writer, writer_after)
        stored = reader.get_document(
            SCOPE, canonical_document_id(SOURCE, "policy/refunds")
        )
        assert stored is not None and stored.revision == "r1"
        assert stored.acl.principals == (FINANCE,)

        with SQLiteBrainStore(path) as fresh_store:
            fresh = CompanyBrain(fresh_store, SCOPE)
            fresh_answer = fresh.answer(QUESTION, user_id="alice")
            warm_answer = warm.answer(QUESTION, user_id="alice")
            assert fresh_answer["disposition"] == "insufficient_evidence"
            assert warm_answer["disposition"] == "insufficient_evidence"
            assert QUOTE not in fresh_answer["answer"]
            assert fresh_answer["answer"] == warm_answer["answer"]
    finally:
        reader.close()
        writer.close()


def test_durable_answer_cache_is_bound_to_scope_and_user_across_reopen(
    tmp_path: Path,
) -> None:
    path = tmp_path / "brain.sqlite"
    acme = document("policy/refunds")
    beta = document(
        "policy/refunds",
        "The beta refund window is 90 days.",
        title="Beta refunds",
    )

    with SQLiteBrainStore(path) as store:
        sync_full(store, acme, scope=SCOPE)
        sync_full(store, beta, scope=OTHER_TENANT)
        store.set_groups(SCOPE, "alice", {"support"})
        store.set_groups(OTHER_TENANT, "alice", {"support"})

        acme_answer = CompanyBrain(store, SCOPE).answer(QUESTION, user_id="alice")
        beta_answer = CompanyBrain(store, OTHER_TENANT).answer(
            QUESTION, user_id="alice"
        )
        assert QUOTE in acme_answer["answer"]
        assert "90 days" in beta_answer["answer"]

    with SQLiteBrainStore(path) as reopened:
        # Each scope keeps its own record: the shared key name never collides.
        scoped = CompanyBrain(reopened, SCOPE).answer(QUESTION, user_id="alice")
        tenant = CompanyBrain(reopened, OTHER_TENANT).answer(QUESTION, user_id="alice")
        assert scoped["cache_hit"] is True
        assert tenant["cache_hit"] is True
        assert QUOTE in scoped["answer"]
        assert "90 days" in tenant["answer"]

        # A user with no membership never inherits another user's cached prose.
        store = reopened
        store.set_groups(SCOPE, "carol", set())
        carol = CompanyBrain(store, SCOPE).answer(QUESTION, user_id="carol")
        assert carol["cache_hit"] is False
        assert carol["disposition"] == "insufficient_evidence"


# --------------------------------------------------------------------------- #
# Stale plans must not be recoverable into a write
# --------------------------------------------------------------------------- #


def test_stale_plan_after_reopen_writes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "brain.sqlite"
    with SQLiteBrainStore(path) as store:
        sync_full(store, document("policy/refunds"))
        stale = plan_for(
            store,
            incremental_page(document("policy/travel")),
            SyncMode.INCREMENTAL,
        )
        # Commit a different plan from the same generation first.
        sync_incremental(store, document("policy/leave", "Leave is twenty days."))
        documents = stored_documents(store)
        state = store.state(SCOPE, SOURCE)

    with SQLiteBrainStore(path) as store:
        with pytest.raises(ValueError, match="generation mismatch"):
            store.apply_plan(SCOPE, stale)
        assert store.state(SCOPE, SOURCE) == state
        assert stored_documents(store) == documents
        assert (
            store.get_document(SCOPE, canonical_document_id(SOURCE, "policy/travel"))
            is None
        )
