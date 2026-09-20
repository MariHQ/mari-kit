"""Cross-process concurrency tests for the durable company brain.

Wave 5 hardens the *between-processes* contract that the earlier waves only
exercised inside a single interpreter.  Every writer here is a real spawned
process that opens its own :class:`SQLiteBrainStore` connection: no store,
connection, cursor, or transaction is shared across a process boundary, and the
tests never assume a shared-connection thread-safe path exists.

Coordination is event based rather than timing based.  Competing writers meet
at a :class:`multiprocessing.Barrier` after each has independently read and
planned from the same committed generation, and a failpoint event makes the
lock order deterministic, so "exactly one commits" is asserted without sleeps.
A reader keeps a warm :class:`CompanyBrain` cache in the parent process while a
separate writer process commits ACL, membership, title, and deletion changes,
and the reader is checked only *after* the writer acknowledges the commit, so a
completed read is never retracted -- it simply stops being the answer once the
live state it described has moved on.

The tests reuse only the public host surface: ``apply_plan``, ``set_groups``,
``state``, ``documents``, ``projection``, ``get_document``, ``access_token``,
and the engine's ``search``/``answer``.  Where a transaction is interrupted the
assertions read the durable store through a fresh connection and compare it to
the pre-transaction snapshot, so a rolled-back plan must be invisible.
"""

from __future__ import annotations

import multiprocessing as mp
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from queue import Empty
from typing import Any

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
from mari_kit.sync import plan_sync

TENANT = "wave5"
SPACE = "brain"
SOURCE = "handbook"
QUESTION = "What is the refund window?"
SUPPORT = Principal(kind="team", identifier="support")
FINANCE = Principal(kind="team", identifier="finance")

SCOPE = ScopeRef(tenant=TENANT, space=SPACE)
_TIMEOUT = 30.0
_JOIN_TIMEOUT = 30.0


def _scope() -> ScopeRef:
    return ScopeRef(tenant=TENANT, space=SPACE)


def _document(
    external_id: str,
    body: str,
    revision: str = "r1",
    *,
    title: str | None = None,
    visibility: str = "connector_scope",
    principals: tuple[Principal, ...] = (),
) -> KnowledgeDocument:
    return KnowledgeDocument(
        source_id=SOURCE,
        external_id=external_id,
        title=title or f"Handbook {external_id}",
        body=body,
        revision=revision,
        acl=DocumentACL(visibility=visibility, principals=principals),
    )


def _refunds(
    *,
    title: str = "Refund policy",
    principals: tuple[Principal, ...] = (SUPPORT,),
    revision: str = "r1",
) -> KnowledgeDocument:
    return _document(
        "policy/refunds",
        "The refund window is 30 days.",
        revision,
        title=title,
        visibility="restricted",
        principals=principals,
    )


def _travel() -> KnowledgeDocument:
    return _document(
        "policy/travel", "Travel requires approval.", title="Travel policy"
    )


def _notice(external_id: str, body: str, revision: str = "v1") -> KnowledgeDocument:
    return _document(
        external_id,
        body,
        revision,
        title=f"Notice {external_id}",
        visibility="public",
    )


def _competing_page(tag: str) -> PollPage:
    return PollPage(
        upserts=(
            _document(
                f"policy/{tag}",
                f"Writer {tag} owns this policy.",
                title=f"Writer {tag} policy",
            ),
        ),
        next_cursor=f"inc:{tag}",
        snapshot_complete=True,
    )


def _full_snapshot_first_page() -> PollPage:
    return PollPage(
        upserts=(_notice("notices/alpha", "Alpha notice body."),),
        next_checkpoint="page:2",
        snapshot_complete=False,
    )


def _full_snapshot_terminal_page() -> PollPage:
    return PollPage(
        upserts=(
            _notice("notices/alpha", "Alpha notice body."),
            _notice("notices/beta", "Beta notice body."),
        ),
        next_cursor="full:done",
        snapshot_complete=True,
    )


def _revised_notice() -> KnowledgeDocument:
    return _notice("notices/refunds", "The refund window is 45 days.", "v2")


def _apply_page(
    store: SQLiteBrainStore,
    page: PollPage,
    *,
    mode: SyncMode = SyncMode.INCREMENTAL,
    scope: ScopeRef | None = None,
    source: str = SOURCE,
):
    target = scope or SCOPE
    plan = plan_sync(store.state(target, source), page, source_id=source, mode=mode)
    store.apply_plan(target, plan)
    return plan


def _apply_change(store: SQLiteBrainStore, name: str) -> None:
    """Apply one named live change on the writer's own connection."""

    scope = _scope()
    if name == "acl":
        _apply_page(
            store,
            PollPage(
                upserts=(_refunds(principals=(FINANCE,)),), snapshot_complete=True
            ),
            scope=scope,
        )
    elif name == "grant":
        store.set_groups(scope, "alice", {"support", "finance"})
    elif name == "title":
        _apply_page(
            store,
            PollPage(
                upserts=(_refunds(title="Legacy notice", principals=(FINANCE,)),),
                snapshot_complete=True,
            ),
            scope=scope,
        )
    elif name == "delete":
        _apply_page(
            store,
            PollPage(
                tombstones=(Tombstone(source_id=SOURCE, external_id="policy/refunds"),),
                snapshot_complete=True,
            ),
            scope=scope,
        )
    else:  # pragma: no cover - test-controlled names only
        raise ValueError(f"unknown change {name!r}")


def _compete_worker(
    db: str,
    instance: str,
    barrier: Any,
    first_locked: Any,
    second_attempting: Any,
    attempts: Any,
    timeout: float,
) -> None:
    """Plan from the shared generation, then race a deliberately ordered commit."""

    scope = _scope()
    store = SQLiteBrainStore(db)
    try:
        plan = plan_sync(
            store.state(scope, SOURCE),
            _competing_page(instance),
            source_id=SOURCE,
            mode=SyncMode.INCREMENTAL,
        )
        barrier.wait(timeout=timeout)
        if instance == "0":

            def hold_then_commit(stage: str) -> None:
                if stage == "after_documents":
                    first_locked.set()
                    if not second_attempting.wait(timeout):
                        raise RuntimeError("second writer never attempted")

            store.apply_plan(scope, plan, failpoint=hold_then_commit)
            attempts.put((instance, "committed", str(plan.expected_generation)))
        else:
            if not first_locked.wait(timeout):
                attempts.put((instance, "error", "first writer never locked"))
                return
            second_attempting.set()
            try:
                store.apply_plan(scope, plan)
            except ValueError as error:
                attempts.put((instance, "mismatch", str(error)))
            else:
                attempts.put((instance, "committed", str(plan.expected_generation)))
    except BaseException as error:  # noqa: BLE001 - reported to the parent
        attempts.put((instance, "error", repr(error)))
    finally:
        store.close()


def _writer_worker(db: str, commands: Any, results: Any, timeout: float) -> None:
    """A persistent writer process driven by named commands over a queue."""

    store = SQLiteBrainStore(db)
    try:
        while True:
            try:
                command = commands.get(timeout=timeout)
            except Empty:
                results.put(("error", "command wait timed out"))
                return
            if command == "stop":
                results.put(("stopped", "ok"))
                return
            try:
                _apply_change(store, command)
            except BaseException as error:  # noqa: BLE001 - reported to the parent
                results.put((command, f"error: {error!r}"))
                return
            results.put((command, "ok"))
    finally:
        store.close()


def _full_sync_worker(db: str, page: str, results: Any) -> None:
    """Apply one authoritative full-sync page in a fresh process."""

    scope = _scope()
    store = SQLiteBrainStore(db)
    try:
        chosen = (
            _full_snapshot_first_page()
            if page == "first"
            else _full_snapshot_terminal_page()
        )
        plan = plan_sync(
            store.state(scope, SOURCE), chosen, source_id=SOURCE, mode=SyncMode.FULL
        )
        store.apply_plan(scope, plan)
        results.put((page, plan.expected_generation, plan.state.generation))
    except BaseException as error:  # noqa: BLE001 - reported to the parent
        results.put((page, "error", repr(error)))
    finally:
        store.close()


def _rollback_worker(db: str, proceed: Any, results: Any, timeout: float) -> None:
    """Roll back an edit, wait for the parent, then commit the same plan."""

    scope = _scope()
    store = SQLiteBrainStore(db)
    try:
        plan = plan_sync(
            store.state(scope, SOURCE),
            PollPage(upserts=(_revised_notice(),), snapshot_complete=True),
            source_id=SOURCE,
            mode=SyncMode.INCREMENTAL,
        )

        def fail(stage: str) -> None:
            if stage == "before_commit":
                raise RuntimeError("rollback-requested")

        try:
            store.apply_plan(scope, plan, failpoint=fail)
        except RuntimeError as error:
            results.put(("rolled-back", str(error)))
        else:
            results.put(("unexpected-commit", "failpoint was not reached"))
            return
        if not proceed.wait(timeout):
            results.put(("timeout", "parent never proceeded"))
            return
        store.apply_plan(scope, plan)
        results.put(("committed", plan.state.generation))
    except BaseException as error:  # noqa: BLE001 - reported to the parent
        results.put(("error", repr(error)))
    finally:
        store.close()


@contextmanager
def _child(ctx: Any, target: Callable[..., None], *args: Any) -> Iterator[Any]:
    """Start one spawned process and always reap it with a bounded wait."""

    process = ctx.Process(target=target, args=args)
    process.start()
    try:
        yield process
    finally:
        process.join(_JOIN_TIMEOUT)
        if process.is_alive():
            process.terminate()
            process.join(_JOIN_TIMEOUT)
        if process.is_alive():
            process.kill()
            process.join(_JOIN_TIMEOUT)


def test_competing_writers_from_same_generation_commit_exactly_one(
    tmp_path: Path,
) -> None:
    db = tmp_path / "brain.sqlite"
    with SQLiteBrainStore(db) as store:
        _apply_page(
            store,
            PollPage(upserts=(_refunds(), _travel()), snapshot_complete=True),
            mode=SyncMode.FULL,
        )
        base_state = store.state(SCOPE, SOURCE)
        base_documents = {item.document_id: item for item in store.documents(SCOPE)}
        base_token = store.access_token(SCOPE, "alice")

    ctx = mp.get_context("spawn")
    barrier = ctx.Barrier(2)
    first_locked = ctx.Event()
    second_attempting = ctx.Event()
    attempts = ctx.Queue()
    with _child(
        ctx,
        _compete_worker,
        str(db),
        "0",
        barrier,
        first_locked,
        second_attempting,
        attempts,
        _TIMEOUT,
    ):
        with _child(
            ctx,
            _compete_worker,
            str(db),
            "1",
            barrier,
            first_locked,
            second_attempting,
            attempts,
            _TIMEOUT,
        ):
            outcomes = [attempts.get(timeout=_TIMEOUT) for _ in range(2)]

    by_instance = {instance: status for instance, status, _ in outcomes}
    assert sorted(by_instance.values()) == ["committed", "mismatch"], outcomes
    winner = next(
        instance for instance, status in by_instance.items() if status == "committed"
    )
    loser = next(
        instance for instance, status in by_instance.items() if status == "mismatch"
    )
    assert "generation mismatch" in next(
        detail for instance, _, detail in outcomes if instance == loser
    )

    winning_plan = plan_sync(
        base_state, _competing_page(winner), source_id=SOURCE, mode=SyncMode.INCREMENTAL
    )
    expected_documents = dict(base_documents)
    for document in winning_plan.upserts:
        expected_documents[document.document_id] = document
    for tombstone in winning_plan.deletes:
        expected_documents.pop(tombstone.document_id, None)

    with SQLiteBrainStore(db) as store:
        state = store.state(SCOPE, SOURCE)
        documents = {item.document_id: item for item in store.documents(SCOPE)}
        projection = store.projection(SCOPE)
        token = store.access_token(SCOPE, "alice")

    assert state == winning_plan.state
    assert state.generation == base_state.generation + 1
    assert documents == expected_documents
    assert projection == {
        item.document_id: item.body for item in expected_documents.values()
    }
    assert set(projection) == set(documents)
    # Exactly one document epoch bump: the loser wrote nothing, not even an epoch.
    assert token.doc_epoch == base_token.doc_epoch + 1
    assert canonical_document_id(SOURCE, f"policy/{loser}") not in documents
    assert canonical_document_id(SOURCE, f"policy/{winner}") in documents


def test_warmed_reader_observes_cross_process_changes_after_ack(
    tmp_path: Path,
) -> None:
    db = tmp_path / "brain.sqlite"
    with SQLiteBrainStore(db) as store:
        _apply_page(
            store,
            PollPage(upserts=(_refunds(), _travel()), snapshot_complete=True),
            mode=SyncMode.FULL,
        )
        store.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(store, SCOPE)

        # Warm both the authorized-view cache and the durable answer cache.
        assert brain.search("refund", user_id="alice")[0] == _refunds()
        warm = brain.answer(QUESTION, user_id="alice")
        assert warm["disposition"] == "grounded"
        assert "30 days" in warm["answer"]
        assert brain.answer(QUESTION, user_id="alice")["cache_hit"] is True
        baseline = store.access_token(SCOPE, "alice")

        ctx = mp.get_context("spawn")
        commands = ctx.Queue()
        results = ctx.Queue()
        with _child(ctx, _writer_worker, str(db), commands, results, _TIMEOUT):

            def ack(command: str) -> None:
                commands.put(command)
                assert results.get(timeout=_TIMEOUT) == (command, "ok")

            # 1. Same-revision ACL change: revision stays "r1", access changes.
            ack("acl")
            live = store.get_document(SCOPE, _refunds().document_id)
            assert live is not None and live.revision == "r1"
            assert live.acl.principals == (FINANCE,)
            assert (
                store.access_token(SCOPE, "alice").doc_epoch == baseline.doc_epoch + 1
            )
            assert brain.search("refund", user_id="alice") == ()
            after_acl = brain.answer(QUESTION, user_id="alice")
            assert after_acl["cache_hit"] is False
            assert "30 days" not in after_acl["answer"]
            # Completed reads are not retracted: the earlier answer still stands.
            assert "30 days" in warm["answer"]

            # 2. Membership grant: no document change, only the reader's groups.
            ack("grant")
            assert (
                store.access_token(SCOPE, "alice").membership_epoch
                == baseline.membership_epoch + 1
            )
            granted = brain.search("refund", user_id="alice")
            assert granted and granted[0] == _refunds(principals=(FINANCE,))
            assert brain.answer(QUESTION, user_id="alice")["disposition"] == "grounded"

            # 3. Title-only change at the same revision rebuilds the warm index.
            assert brain.search("legacy", user_id="alice") == ()
            ack("title")
            titled = store.get_document(SCOPE, _refunds().document_id)
            assert titled is not None and titled.revision == "r1"
            assert titled.title == "Legacy notice"
            assert [item.title for item in brain.search("legacy", user_id="alice")] == [
                "Legacy notice"
            ]

            # 4. Deletion removes the document from every subsequent read.
            ack("delete")
            assert store.get_document(SCOPE, _refunds().document_id) is None
            assert brain.search("refund", user_id="alice") == ()
            deleted = brain.answer(QUESTION, user_id="alice")
            assert deleted["cache_hit"] is False
            assert "30 days" not in deleted["answer"]

            commands.put("stop")
            assert results.get(timeout=_TIMEOUT) == ("stopped", "ok")


def test_source_progress_survives_restart_and_resumes(tmp_path: Path) -> None:
    db = tmp_path / "brain.sqlite"
    ctx = mp.get_context("spawn")

    first = ctx.Queue()
    with _child(ctx, _full_sync_worker, str(db), "first", first):
        assert first.get(timeout=_TIMEOUT) == ("first", 0, 1)

    alpha_id = _notice("notices/alpha", "Alpha notice body.").document_id
    with SQLiteBrainStore(db) as store:
        resumed = store.state(SCOPE, SOURCE)
        assert resumed.active_mode is SyncMode.FULL
        assert resumed.checkpoint == "page:2"
        assert resumed.cursor is None
        assert resumed.full_seen == frozenset({alpha_id})
        assert resumed.generation == 1
        assert {item.document_id for item in store.documents(SCOPE)} == {alpha_id}

    terminal = ctx.Queue()
    with _child(ctx, _full_sync_worker, str(db), "terminal", terminal):
        assert terminal.get(timeout=_TIMEOUT) == ("terminal", 1, 2)

    expected_alpha = _notice("notices/alpha", "Alpha notice body.")
    expected_beta = _notice("notices/beta", "Beta notice body.")
    with SQLiteBrainStore(db) as store:
        final = store.state(SCOPE, SOURCE)
        assert final.active_mode is None
        assert final.checkpoint is None
        assert final.cursor == "full:done"
        assert final.full_seen == frozenset()
        assert final.generation == 2
        documents = {item.document_id: item for item in store.documents(SCOPE)}
        assert documents == {
            expected_alpha.document_id: expected_alpha,
            expected_beta.document_id: expected_beta,
        }
        assert store.projection(SCOPE) == {
            item.document_id: item.body for item in documents.values()
        }


def test_rolled_back_plan_is_invisible_and_the_retry_is_observed(
    tmp_path: Path,
) -> None:
    db = tmp_path / "brain.sqlite"
    with SQLiteBrainStore(db) as store:
        _apply_page(
            store,
            PollPage(
                upserts=(_notice("notices/refunds", "The refund window is 30 days."),),
                snapshot_complete=True,
            ),
            mode=SyncMode.FULL,
        )
        brain = CompanyBrain(store, SCOPE)
        warm = brain.answer(QUESTION, user_id="alice")
        assert warm["disposition"] == "grounded"
        assert "30 days" in warm["answer"]
        assert brain.answer(QUESTION, user_id="alice")["cache_hit"] is True
        base_state = store.state(SCOPE, SOURCE)
        base_documents = {item.document_id: item for item in store.documents(SCOPE)}
        base_projection = store.projection(SCOPE)
        base_token = store.access_token(SCOPE, "alice")

        ctx = mp.get_context("spawn")
        proceed = ctx.Event()
        results = ctx.Queue()
        with _child(ctx, _rollback_worker, str(db), proceed, results, _TIMEOUT):
            status, detail = results.get(timeout=_TIMEOUT)
            assert status == "rolled-back", detail

            # The interrupted transaction left no trace on any durable surface.
            assert store.state(SCOPE, SOURCE) == base_state
            assert {
                item.document_id: item for item in store.documents(SCOPE)
            } == base_documents
            assert store.projection(SCOPE) == base_projection
            assert store.access_token(SCOPE, "alice") == base_token
            # A rolled-back write must not invalidate a warm read.
            assert brain.answer(QUESTION, user_id="alice")["cache_hit"] is True

            proceed.set()
            assert results.get(timeout=_TIMEOUT) == (
                "committed",
                base_state.generation + 1,
            )

        revised = _revised_notice()
        assert store.get_document(SCOPE, revised.document_id) == revised
        observed = brain.answer(QUESTION, user_id="alice")
        assert observed["cache_hit"] is False
        assert "45 days" in observed["answer"]
