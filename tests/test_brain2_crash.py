"""Process-death durability tests for the wave-2 durable company brain.

Every crash is a real ``os._exit`` inside a child process: no ``finally``
blocks, no context-manager cleanup, and no graceful SQLite close.  After each
crash the database is reopened in a brand-new process and compared against an
expected snapshot produced independently by Mari Kit's pure ``plan_sync``
reducer, so the assertions never call the code path under test to build their
own expectation.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path

import pytest

from examples.company_brains.durable import crash_worker as worker
from examples.company_brains.durable import store as durable_store
from mari_kit import KnowledgeDocument, SyncMode, canonical_document_id
from mari_kit.json import to_json_value
from mari_kit.sync import SyncPlan, SyncState, plan_sync

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = worker.SOURCE_ID
SCOPE = worker.DEFAULT_SCOPE


def _run(
    db: Path, mode: str, *extra: object, timeout: float = 60.0
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "-m",
        "examples.company_brains.durable.crash_worker",
        "--db",
        str(db),
        "--mode",
        mode,
        *(str(item) for item in extra),
    ]
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _start(db: Path, mode: str, *extra: object) -> subprocess.Popen[str]:
    command = [
        sys.executable,
        "-m",
        "examples.company_brains.durable.crash_worker",
        "--db",
        str(db),
        "--mode",
        mode,
        *(str(item) for item in extra),
    ]
    return subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _reduce(
    documents: Iterable[KnowledgeDocument], plan: SyncPlan
) -> dict[str, KnowledgeDocument]:
    current = {item.document_id: item for item in documents}
    for document in plan.upserts:
        current[document.document_id] = document
    for tombstone in plan.deletes:
        current.pop(tombstone.document_id, None)
    return current


def _reference(
    pages: Iterable[tuple[object, SyncMode]],
) -> tuple[dict[str, KnowledgeDocument], SyncState, list[SyncPlan]]:
    """Replay pages with the pure planner; independent of any SQLite code."""

    state = SyncState()
    documents: dict[str, KnowledgeDocument] = {}
    plans: list[SyncPlan] = []
    for page, mode in pages:
        plan = plan_sync(state, page, source_id=SOURCE_ID, mode=mode)  # type: ignore[arg-type]
        plans.append(plan)
        documents = _reduce(documents.values(), plan)
        state = plan.state
    return documents, state, plans


def _projection(documents: Iterable[KnowledgeDocument]) -> dict[str, str]:
    return {item.document_id: item.body for item in documents}


def _stored(
    db: Path,
) -> tuple[tuple[KnowledgeDocument, ...], dict[str, str], SyncState]:
    with durable_store.SQLiteBrainStore(db) as store:
        documents = store.documents(SCOPE)
        projection = store.projection(SCOPE)
        state = store.state(SCOPE, SOURCE_ID)
    return documents, projection, state


@pytest.mark.parametrize("stage", worker.STAGES)
def test_process_death_at_each_failpoint_is_all_or_nothing(
    tmp_path: Path, stage: str
) -> None:
    db = tmp_path / "brain.db"
    assert _run(db, "seed").returncode == 0

    with durable_store.SQLiteBrainStore(db) as store:
        base_documents = store.documents(SCOPE)
        base_projection = store.projection(SCOPE)
        base_state = store.state(SCOPE, SOURCE_ID)
    incremental = plan_sync(
        base_state,
        worker.incremental_page(),
        source_id=SOURCE_ID,
        mode=SyncMode.INCREMENTAL,
    )

    marker = tmp_path / f"{stage}.marker"
    result = _run(
        db,
        "incremental-crash",
        "--stage",
        stage,
        "--marker",
        str(marker),
    )
    assert result.returncode == 0, result.stderr
    assert marker.read_text(encoding="utf-8") == stage, (
        "the failpoint stage was never reached"
    )

    documents, projection, state = _stored(db)
    if stage == "after_commit":
        expected_documents = _reduce(base_documents, incremental)
        expected_state = incremental.state
    else:
        expected_documents = {item.document_id: item for item in base_documents}
        expected_state = base_state

    assert state == expected_state
    assert {item.document_id: item for item in documents} == expected_documents
    assert projection == _projection(expected_documents.values())
    assert set(projection) == {item.document_id for item in documents}

    if stage != "after_commit":
        assert base_state.generation == expected_state.generation
        assert incremental.state.generation == base_state.generation + 1
        assert (
            canonical_document_id(SOURCE_ID, "policy/security")
            not in expected_documents
        )
        assert projection == base_projection


def test_partial_full_snapshot_resumes_in_fresh_processes(tmp_path: Path) -> None:
    db = tmp_path / "brain.db"
    pages = worker.full_snapshot_pages()

    expected_documents, expected_state, plans = _reference(
        (page, SyncMode.FULL) for page in pages
    )
    after_first = _reduce((), plans[0])
    after_second = _reduce(after_first.values(), plans[1])

    assert _run(db, "full-page", "--page", 0).returncode == 0
    documents, projection, state = _stored(db)
    assert state == plans[0].state
    assert {item.document_id: item for item in documents} == after_first
    assert projection == _projection(after_first.values())

    marker = tmp_path / "page1.marker"
    crashed = _run(
        db,
        "full-page",
        "--page",
        1,
        "--stage",
        "after_projection",
        "--marker",
        str(marker),
    )
    assert crashed.returncode == 0, crashed.stderr
    assert marker.read_text(encoding="utf-8") == "after_projection"

    documents, projection, state = _stored(db)
    assert state == plans[0].state, "partial page 1 was committed"
    assert {item.document_id: item for item in documents} == after_first
    assert projection == _projection(after_first.values())

    assert _run(db, "full-page", "--page", 1).returncode == 0
    documents, projection, state = _stored(db)
    assert state == plans[1].state
    assert {item.document_id: item for item in documents} == after_second

    assert _run(db, "full-page", "--page", 2).returncode == 0
    documents, projection, state = _stored(db)
    assert expected_state.active_mode is None
    assert expected_state.full_seen == frozenset()
    assert expected_state.generation == len(pages)
    assert state == expected_state
    stored = {item.document_id: item for item in documents}
    assert stored == expected_documents
    assert projection == _projection(expected_documents.values())
    assert set(projection) == {item.document_id for item in documents}


def test_fresh_process_read_matches_committed_state(tmp_path: Path) -> None:
    db = tmp_path / "brain.db"
    assert _run(db, "seed").returncode == 0
    assert _run(db, "incremental-apply").returncode == 0

    expected_documents, expected_state, _ = _reference(
        (
            (worker.seed_page(), SyncMode.FULL),
            (worker.incremental_page(), SyncMode.INCREMENTAL),
        )
    )

    result = _run(db, "read")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)

    assert payload["state"] == json.loads(json.dumps(to_json_value(expected_state)))
    listed = {item["document_id"]: item for item in payload["documents"]}
    assert set(listed) == set(expected_documents)
    for document_id, item in listed.items():
        expected = expected_documents[document_id]
        assert item["revision"] == expected.revision
        assert item["body"] == expected.body
    assert payload["projection"] == _projection(expected_documents.values())

    with durable_store.SQLiteBrainStore(db) as store:
        assert [item.document_id for item in store.documents(SCOPE)] == [
            item.document_id for item in store.documents(SCOPE)
        ]


def test_rejected_foreign_source_plan_writes_nothing(tmp_path: Path) -> None:
    db = tmp_path / "brain.db"
    assert _run(db, "seed").returncode == 0

    with durable_store.SQLiteBrainStore(db) as store:
        base_documents = store.documents(SCOPE)
        base_projection = store.projection(SCOPE)
        base_state = store.state(SCOPE, SOURCE_ID)

    plan = plan_sync(
        base_state,
        worker.incremental_page(),
        source_id=SOURCE_ID,
        mode=SyncMode.INCREMENTAL,
    )
    foreign = KnowledgeDocument(
        source_id="other-source",
        external_id="policy/leave",
        title="Foreign leave policy",
        body="Foreign body that must never be written.",
        revision="r1",
    )
    assert plan.expected_generation == base_state.generation

    with durable_store.SQLiteBrainStore(db) as store:
        with pytest.raises(ValueError, match="foreign"):
            store.apply_plan(SCOPE, replace(plan, upserts=(foreign,)))

    documents, projection, state = _stored(db)
    assert state == base_state
    assert {item.document_id: item for item in documents} == {
        item.document_id: item for item in base_documents
    }
    assert projection == base_projection


def test_competing_writers_from_one_generation_commit_exactly_one(
    tmp_path: Path,
) -> None:
    db = tmp_path / "brain.db"
    assert _run(db, "seed").returncode == 0

    with durable_store.SQLiteBrainStore(db) as store:
        base_documents = store.documents(SCOPE)
        base_state = store.state(SCOPE, SOURCE_ID)

    barrier = tmp_path / "barrier"
    processes = [
        (_start(db, "compete", "--instance", tag, "--barrier", str(barrier)), tag)
        for tag in ("0", "1")
    ]
    outputs = {tag: process.communicate(timeout=60.0) for process, tag in processes}
    codes = {tag: process.returncode for process, tag in processes}
    assert sorted(codes.values()) == [0, 1], outputs

    loser = next(tag for tag, code in codes.items() if code != 0)
    assert "generation mismatch" in outputs[loser][1]
    winner = next(tag for tag, code in codes.items() if code == 0)

    winning_plan = plan_sync(
        base_state,
        worker.competing_page(winner),
        source_id=SOURCE_ID,
        mode=SyncMode.INCREMENTAL,
    )
    expected_documents = _reduce(base_documents, winning_plan)

    documents, projection, state = _stored(db)
    assert state == winning_plan.state
    assert state.generation == base_state.generation + 1
    assert {item.document_id: item for item in documents} == expected_documents
    assert projection == _projection(expected_documents.values())

    present = {
        tag
        for tag in ("0", "1")
        if canonical_document_id(SOURCE_ID, f"policy/{tag}")
        in {item.document_id for item in documents}
    }
    assert present == {winner}
