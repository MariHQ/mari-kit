"""Wave-7 lifecycle tests for the durable SQLite company-brain store.

Earlier waves pinned serialization, crash atomicity, and cross-process
concurrency.  This file targets the lifecycle edges of the same host-owned
store:

* restart -- documents, projection, state, memberships, cache, and the access
  counters survive close/reopen and a new plan continues from the durable
  generation;
* transaction failure -- when SQLite rolls a transaction back itself (for
  example a ``RAISE(ROLLBACK)`` trigger) the store must re-raise the original
  error instead of masking it with a secondary "cannot rollback" error, and the
  connection must remain usable; an interrupted plan rolls back everything,
  including the access counters;
* closed connection -- a closed store rejects operations with the standard
  ``sqlite3.ProgrammingError`` and ``close`` stays idempotent;
* path handling -- directories, ``:memory:``, nested parent creation, path-like
  objects, and an empty path (which SQLite would silently open as a throwaway
  temporary database);
* checkpoint durability -- an incomplete full-snapshot checkpoint survives a
  failed plan and a restart, and is cleared only by the terminal page.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from examples.company_brains.durable import store as store_module
from examples.company_brains.durable.store import SQLiteBrainStore
from mari_kit import (
    DocumentACL,
    KnowledgeDocument,
    PollPage,
    ScopeRef,
    SyncMode,
)
from mari_kit.sync import SyncPlan, SyncState, plan_sync

SOURCE = "kb:wave7"
SCOPE = ScopeRef(tenant="wave7", space="brain")


def document(
    external_id: str,
    body: str,
    revision: str = "r1",
    *,
    visibility: str = "connector_scope",
) -> KnowledgeDocument:
    return KnowledgeDocument(
        source_id=SOURCE,
        external_id=external_id,
        title=external_id.replace("/", " ").title(),
        body=body,
        revision=revision,
        acl=DocumentACL(visibility=visibility),
    )


def full_plan(
    store: SQLiteBrainStore, documents: tuple[KnowledgeDocument, ...]
) -> SyncPlan:
    return plan_sync(
        store.state(SCOPE, SOURCE),
        PollPage(
            upserts=documents,
            next_cursor="cursor:full:done",
            snapshot_complete=True,
        ),
        source_id=SOURCE,
        mode=SyncMode.FULL,
    )


def incremental_plan(
    store: SQLiteBrainStore, upserts: tuple[KnowledgeDocument, ...]
) -> SyncPlan:
    return plan_sync(
        store.state(SCOPE, SOURCE),
        PollPage(
            upserts=upserts,
            next_cursor="cursor:inc:1",
            snapshot_complete=True,
        ),
        source_id=SOURCE,
        mode=SyncMode.INCREMENTAL,
    )


def partial_plan(
    store: SQLiteBrainStore,
    documents: tuple[KnowledgeDocument, ...],
    *,
    checkpoint: str,
) -> SyncPlan:
    return plan_sync(
        store.state(SCOPE, SOURCE),
        PollPage(
            upserts=documents,
            next_checkpoint=checkpoint,
            snapshot_complete=False,
        ),
        source_id=SOURCE,
        mode=SyncMode.FULL,
    )


def sync_full(
    store: SQLiteBrainStore, documents: tuple[KnowledgeDocument, ...]
) -> SyncPlan:
    plan = full_plan(store, documents)
    store.apply_plan(SCOPE, plan)
    return plan


# --------------------------------------------------------------------------- #
# Restart
# --------------------------------------------------------------------------- #


def test_restart_preserves_documents_projection_state_membership_cache_and_epochs(
    tmp_path: Path,
) -> None:
    path = tmp_path / "brain.sqlite3"
    access = document("policy/access", "Access needs approval.", "r1")

    with SQLiteBrainStore(path) as store:
        plan = sync_full(store, (access,))
        store.set_groups(SCOPE, "alice", {"security", "managers"})
        store.set_groups(SCOPE, "alice", {"security"})
        store.save_cache(SCOPE, "q:access", {"answer": "manager"})
        token = store.access_token(SCOPE, "alice")

    with SQLiteBrainStore(path) as reopened:
        assert reopened.documents(SCOPE) == (access,)
        assert reopened.get_document(SCOPE, access.document_id) == access
        assert reopened.projection(SCOPE) == {access.document_id: access.body}
        assert reopened.state(SCOPE, SOURCE) == plan.state
        assert reopened.groups(SCOPE, "alice") == frozenset({"security"})
        assert reopened.load_cache(SCOPE, "q:access") == {"answer": "manager"}
        assert reopened.access_token_snapshot(SCOPE, "alice")[0] == token

        follow_up = incremental_plan(
            reopened, (document("policy/travel", "Travel needs approval.", "r1"),)
        )
        assert follow_up.expected_generation == plan.state.generation
        reopened.apply_plan(SCOPE, follow_up)
        assert reopened.state(SCOPE, SOURCE) == follow_up.state
        assert reopened.access_token(SCOPE, "alice").doc_epoch == token.doc_epoch + 1

    with SQLiteBrainStore(path) as reopened:
        assert reopened.state(SCOPE, SOURCE) == follow_up.state
        assert set(reopened.projection(SCOPE)) == {
            access.document_id,
            document("policy/travel", "Travel needs approval.", "r1").document_id,
        }


def test_reopened_store_resumes_an_incomplete_full_snapshot_from_checkpoint(
    tmp_path: Path,
) -> None:
    path = tmp_path / "brain.sqlite3"
    alpha = document("policy/alpha", "Alpha body.", "r1")
    beta = document("policy/beta", "Beta body.", "r1")

    with SQLiteBrainStore(path) as store:
        store.apply_plan(SCOPE, partial_plan(store, (alpha,), checkpoint="page:2"))
        checkpointed = store.state(SCOPE, SOURCE)
        assert checkpointed.active_mode is SyncMode.FULL
        assert checkpointed.checkpoint == "page:2"
        assert checkpointed.full_seen == frozenset({alpha.document_id})

    with SQLiteBrainStore(path) as reopened:
        assert reopened.state(SCOPE, SOURCE) == checkpointed
        assert reopened.documents(SCOPE) == (alpha,)

        terminal = plan_sync(
            reopened.state(SCOPE, SOURCE),
            PollPage(
                upserts=(beta,),
                next_cursor="cursor:full:done",
                snapshot_complete=True,
            ),
            source_id=SOURCE,
            mode=SyncMode.FULL,
        )
        reopened.apply_plan(SCOPE, terminal)

        final = reopened.state(SCOPE, SOURCE)
        assert final.active_mode is None
        assert final.checkpoint is None
        assert final.full_seen == frozenset()
        assert set(reopened.projection(SCOPE)) == {
            alpha.document_id,
            beta.document_id,
        }


# --------------------------------------------------------------------------- #
# Transaction failures
# --------------------------------------------------------------------------- #


def test_set_groups_auto_rollback_preserves_error_membership_and_connection(
    tmp_path: Path,
) -> None:
    with SQLiteBrainStore(tmp_path / "brain.sqlite3") as store:
        store.set_groups(SCOPE, "alice", {"support"})
        before = store.access_token(SCOPE, "alice")
        store._connection.execute(
            "CREATE TRIGGER reject_group BEFORE INSERT ON groups "
            "BEGIN SELECT RAISE(ROLLBACK, 'membership update rejected'); END"
        )

        with pytest.raises(sqlite3.IntegrityError, match="membership update rejected"):
            store.set_groups(SCOPE, "alice", {"finance"})

        assert store.groups(SCOPE, "alice") == frozenset({"support"})
        assert store.access_token(SCOPE, "alice") == before
        assert not store._connection.in_transaction

        store._connection.execute("DROP TRIGGER reject_group")
        store.set_groups(SCOPE, "alice", {"finance"})
        assert store.groups(SCOPE, "alice") == frozenset({"finance"})
        assert store.access_token(SCOPE, "alice").membership_epoch == (
            before.membership_epoch + 1
        )


def test_apply_plan_auto_rollback_preserves_error_and_whole_plan(
    tmp_path: Path,
) -> None:
    with SQLiteBrainStore(tmp_path / "brain.sqlite3") as store:
        sync_full(store, (document("policy/access", "Access needs approval.", "r1"),))
        before_state = store.state(SCOPE, SOURCE)
        before_documents = store.documents(SCOPE)
        before_projection = store.projection(SCOPE)
        before_token = store.access_token(SCOPE, "alice")

        store._connection.execute(
            "CREATE TRIGGER reject_projection BEFORE INSERT ON projections "
            "BEGIN SELECT RAISE(ROLLBACK, 'projection write rejected'); END"
        )
        travel = document("policy/travel", "Travel needs approval.", "r1")
        plan = incremental_plan(store, (travel,))

        with pytest.raises(sqlite3.IntegrityError, match="projection write rejected"):
            store.apply_plan(SCOPE, plan)

        assert store.state(SCOPE, SOURCE) == before_state
        assert store.documents(SCOPE) == before_documents
        assert store.projection(SCOPE) == before_projection
        assert store.access_token(SCOPE, "alice") == before_token
        assert not store._connection.in_transaction

        store._connection.execute("DROP TRIGGER reject_projection")
        store.apply_plan(SCOPE, plan)
        assert store.state(SCOPE, SOURCE) == plan.state
        assert store.get_document(SCOPE, travel.document_id) == travel


def test_access_counter_failure_rolls_back_documents_projection_and_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    added = document("policy/travel", "Travel needs approval.", "r1")

    with SQLiteBrainStore(tmp_path / "brain.sqlite3") as store:
        sync_full(store, (document("policy/access", "Access needs approval.", "r1"),))
        before_state = store.state(SCOPE, SOURCE)
        before_documents = store.documents(SCOPE)
        before_projection = store.projection(SCOPE)
        before_token = store.access_token(SCOPE, "alice")
        plan = incremental_plan(store, (added,))

        def fail(_connection: sqlite3.Connection, _scope: ScopeRef) -> None:
            raise RuntimeError("epoch bump failed")

        monkeypatch.setattr(store_module, "_bump_scope_epoch", fail)
        with pytest.raises(RuntimeError, match="epoch bump failed"):
            store.apply_plan(SCOPE, plan)

        assert store.state(SCOPE, SOURCE) == before_state
        assert store.documents(SCOPE) == before_documents
        assert store.projection(SCOPE) == before_projection
        assert store.access_token(SCOPE, "alice") == before_token

        monkeypatch.undo()
        store.apply_plan(SCOPE, plan)
        assert store.state(SCOPE, SOURCE) == plan.state
        assert store.get_document(SCOPE, added.document_id) == added


# --------------------------------------------------------------------------- #
# Closed connection lifecycle
# --------------------------------------------------------------------------- #


def test_closed_store_operations_raise_programming_error_and_close_is_idempotent(
    tmp_path: Path,
) -> None:
    store = SQLiteBrainStore(tmp_path / "brain.sqlite3")
    plan = full_plan(
        store, (document("policy/access", "Access needs approval.", "r1"),)
    )
    store.close()

    calls = [
        lambda: store.state(SCOPE, SOURCE),
        lambda: store.documents(SCOPE),
        lambda: store.get_document(SCOPE, "missing"),
        lambda: store.projection(SCOPE),
        lambda: store.set_groups(SCOPE, "alice", {"support"}),
        lambda: store.groups(SCOPE, "alice"),
        lambda: store.access_snapshot(SCOPE, "alice"),
        lambda: store.access_token(SCOPE, "alice"),
        lambda: store.access_token_snapshot(SCOPE, "alice"),
        lambda: store.save_cache(SCOPE, "q", {"answer": "x"}),
        lambda: store.load_cache(SCOPE, "q"),
        lambda: store.apply_plan(SCOPE, plan),
    ]
    for call in calls:
        with pytest.raises(sqlite3.ProgrammingError):
            call()

    store.close()  # Closing an already-closed store must not raise.


def test_context_manager_closes_the_connection(tmp_path: Path) -> None:
    with SQLiteBrainStore(tmp_path / "brain.sqlite3") as store:
        sync_full(store, (document("policy/access", "Access needs approval.", "r1"),))
        assert len(store.documents(SCOPE)) == 1

    with pytest.raises(sqlite3.ProgrammingError):
        store.documents(SCOPE)


# --------------------------------------------------------------------------- #
# Path handling
# --------------------------------------------------------------------------- #


def test_memory_path_is_private_to_the_instance() -> None:
    first = SQLiteBrainStore(":memory:")
    try:
        sync_full(first, (document("policy/access", "Access needs approval.", "r1"),))
        assert len(first.documents(SCOPE)) == 1
    finally:
        first.close()

    second = SQLiteBrainStore(":memory:")
    try:
        assert second.documents(SCOPE) == ()
        assert second.state(SCOPE, SOURCE) == SyncState()
    finally:
        second.close()


def test_existing_directory_path_stores_brain_sqlite3_and_survives_restart(
    tmp_path: Path,
) -> None:
    store = SQLiteBrainStore(tmp_path)
    try:
        assert Path(store.path) == tmp_path / "brain.sqlite3"
        sync_full(store, (document("policy/access", "Access needs approval.", "r1"),))
    finally:
        store.close()

    reopened = SQLiteBrainStore(tmp_path)
    try:
        assert len(reopened.documents(SCOPE)) == 1
    finally:
        reopened.close()


def test_nested_parent_directories_are_created(tmp_path: Path) -> None:
    path = tmp_path / "deeply" / "nested" / "brain.sqlite3"
    assert not path.parent.exists()

    store = SQLiteBrainStore(path)
    store.close()

    assert path.exists()


def test_pathlike_and_string_paths_address_the_same_database(tmp_path: Path) -> None:
    path = tmp_path / "brain.sqlite3"
    with SQLiteBrainStore(str(path)) as store:
        sync_full(store, (document("policy/access", "Access needs approval.", "r1"),))

    with SQLiteBrainStore(path) as reopened:
        assert len(reopened.documents(SCOPE)) == 1


def test_empty_path_is_rejected_instead_of_opening_a_temporary_database() -> None:
    # sqlite3 accepts "" as a private temporary database whose rows vanish on
    # close; the store must reject it rather than silently losing writes.
    with pytest.raises(ValueError, match="empty"):
        SQLiteBrainStore("")


# --------------------------------------------------------------------------- #
# Checkpoint durability
# --------------------------------------------------------------------------- #


def test_incomplete_checkpoint_survives_a_failed_plan_and_a_restart(
    tmp_path: Path,
) -> None:
    path = tmp_path / "brain.sqlite3"
    alpha = document("policy/alpha", "Alpha body.", "r1")
    beta = document("policy/beta", "Beta body.", "r1")

    with SQLiteBrainStore(path) as store:
        store.apply_plan(SCOPE, partial_plan(store, (alpha,), checkpoint="page:2"))
        checkpointed = store.state(SCOPE, SOURCE)
        next_page = partial_plan(store, (beta,), checkpoint="page:3")

        def fail(stage: str) -> None:
            if stage == "before_commit":
                raise RuntimeError("interrupted before commit")

        with pytest.raises(RuntimeError, match="interrupted"):
            store.apply_plan(SCOPE, next_page, failpoint=fail)

        assert store.state(SCOPE, SOURCE) == checkpointed
        assert store.documents(SCOPE) == (alpha,)

    with SQLiteBrainStore(path) as reopened:
        resumed = reopened.state(SCOPE, SOURCE)
        assert resumed == checkpointed
        assert resumed.checkpoint == "page:2"
        assert resumed.full_seen == frozenset({alpha.document_id})


def test_noop_intermediate_page_still_persists_its_checkpoint(tmp_path: Path) -> None:
    path = tmp_path / "brain.sqlite3"
    alpha = document("policy/alpha", "Alpha body.", "r1")

    with SQLiteBrainStore(path) as store:
        store.apply_plan(SCOPE, partial_plan(store, (alpha,), checkpoint="page:2"))
        before = store.state(SCOPE, SOURCE)

        page = partial_plan(store, (alpha,), checkpoint="page:3")
        assert page.upserts == () and page.deletes == ()
        store.apply_plan(SCOPE, page)

        after = store.state(SCOPE, SOURCE)
        assert after.generation == before.generation + 1
        assert after.checkpoint == "page:3"
        assert after.full_seen == before.full_seen

    with SQLiteBrainStore(path) as reopened:
        assert reopened.state(SCOPE, SOURCE) == after
        assert reopened.documents(SCOPE) == (alpha,)
