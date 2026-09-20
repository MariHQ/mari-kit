"""Behavioral tests for the continuously synchronized company brain example."""

from __future__ import annotations

import json
from collections.abc import Iterable

import pytest

from examples.company_brains.sync import (
    SOURCE_ID,
    CompanyBrain,
    CompanySource,
    company_document,
    initial_documents,
    run,
)
from mari_kit import PollPage, Principal, SyncMode, Tombstone, canonical_document_id
from mari_kit.sync import apply_sync_plan, plan_sync, stream_sync


def _sync_full(
    brain: CompanyBrain,
    source: CompanySource,
    *,
    page_size: int = 2,
) -> list[dict[str, object]]:
    receipts: list[dict[str, object]] = []
    for index, plan in enumerate(
        stream_sync(
            source.full_pages(page_size),
            brain.sync_state,
            source_id=brain.source_id,
            mode=SyncMode.FULL,
        ),
        start=1,
    ):
        receipts.append(
            brain.apply(plan, mode=SyncMode.FULL, label="snapshot", page=index)
        )
    return receipts


def _document_ids(documents: Iterable[object]) -> list[str]:
    return [document.document_id for document in documents]  # type: ignore[attr-defined]


def test_paginated_full_snapshot_holds_cursor_and_reconciles_only_at_the_end() -> None:
    source = CompanySource(initial_documents())
    brain = CompanyBrain()

    plans = list(
        stream_sync(
            source.full_pages(2),
            brain.sync_state,
            source_id=brain.source_id,
            mode=SyncMode.FULL,
        )
    )

    assert [plan.snapshot_complete for plan in plans] == [False, False, True]
    assert all(plan.deletes == () for plan in plans)
    assert [plan.state.cursor for plan in plans[:2]] == [None, None]
    assert plans[-1].state.cursor == "cursor:full:3"
    assert sum(len(plan.upserts) for plan in plans) == 5

    _sync_full(brain, source)
    assert brain.active_external_ids() == [
        "policy/access",
        "policy/onboarding",
        "policy/payroll",
        "policy/refunds",
        "policy/security",
    ]

    source.drop("policy/access")
    receipts = _sync_full(brain, source)
    assert receipts[-1]["deletes"] == [
        canonical_document_id(SOURCE_ID, "policy/access")
    ]
    assert receipts[-1]["delete_reasons"] == ["absent_from_complete_snapshot"]
    assert "policy/access" not in brain.active


def test_incomplete_full_snapshot_is_mode_locked_and_cannot_resume_incremental() -> (
    None
):
    source = CompanySource(initial_documents())
    brain = CompanyBrain()

    incomplete = plan_sync(
        brain.sync_state,
        source.full_pages(3)[0],
        source_id=brain.source_id,
        mode=SyncMode.FULL,
    )
    assert incomplete.snapshot_complete is False
    assert incomplete.deletes == ()
    brain.apply(incomplete, mode=SyncMode.FULL, label="interrupted")

    assert brain.sync_state.active_mode is SyncMode.FULL
    assert brain.sync_state.cursor is None
    assert brain.sync_state.full_seen

    with pytest.raises(ValueError, match="cannot resume"):
        plan_sync(
            brain.sync_state,
            source.incremental_page(cursor="cursor:incremental"),
            source_id=brain.source_id,
            mode=SyncMode.INCREMENTAL,
        )


def test_incremental_tombstone_removes_live_document_and_manifest_but_not_history() -> (
    None
):
    source = CompanySource(initial_documents())
    brain = CompanyBrain()
    _sync_full(brain, source)
    assert "policy/payroll" in brain.active

    source.drop("policy/payroll")
    plan = plan_sync(
        brain.sync_state,
        source.incremental_page(
            cursor="cursor:incremental:1",
            tombstones=(
                Tombstone(source_id=brain.source_id, external_id="policy/payroll"),
            ),
        ),
        source_id=brain.source_id,
        mode=SyncMode.INCREMENTAL,
    )
    receipt = brain.apply(plan, mode=SyncMode.INCREMENTAL, label="incremental")

    assert receipt["deletes"] == [canonical_document_id(SOURCE_ID, "policy/payroll")]
    assert receipt["delete_reasons"] == ["provider_deleted"]
    assert "policy/payroll" not in brain.active
    assert canonical_document_id(SOURCE_ID, "policy/payroll") not in (
        brain.sync_state.manifest
    )
    assert (
        brain.store.get(SOURCE_ID, "policy/payroll", scope=brain.scope) is not None
    ), "reference store must retain the immutable provider revision"


def test_generation_conflict_rejects_the_competing_plan_without_any_write() -> None:
    source = CompanySource(initial_documents())
    brain = CompanyBrain()
    _sync_full(brain, source)
    base_generation = brain.sync_state.generation

    refunds = company_document(
        "policy/refunds", "Enterprise refunds within sixty days.", "r2"
    )
    travel = company_document("policy/travel", "Travel requires pre-approval.", "r1")
    accepted_plan = plan_sync(
        brain.sync_state,
        source.incremental_page(cursor="cursor:incremental:2", upserts=(refunds,)),
        source_id=brain.source_id,
        mode=SyncMode.INCREMENTAL,
    )
    competing_plan = plan_sync(
        brain.sync_state,
        source.incremental_page(cursor="cursor:concurrent", upserts=(travel,)),
        source_id=brain.source_id,
        mode=SyncMode.INCREMENTAL,
    )
    assert accepted_plan.expected_generation == base_generation
    assert competing_plan.expected_generation == base_generation

    brain.apply(accepted_plan, mode=SyncMode.INCREMENTAL, label="accepted")

    with pytest.raises(ValueError, match="generation mismatch"):
        apply_sync_plan(competing_plan, transaction=brain.transaction())

    assert brain.sync_state.generation == base_generation + 1
    assert "policy/refunds" in brain.active
    assert "policy/travel" not in brain.active
    assert brain.store.get(SOURCE_ID, "policy/travel", scope=brain.scope) is None
    assert len(brain.store.history(SOURCE_ID, "policy/refunds", scope=brain.scope)) == 2


def test_acl_only_observation_is_planned_but_immutable_store_rejects_it() -> None:
    """Host boundary: an ACL-only observation cannot reuse the provider revision.

    ``plan_sync`` fingerprints provider ACL metadata, so this is correctly a
    planned upsert even though ``revision`` is unchanged. The reference
    revision store models immutable revisions and refuses the duplicate, which
    leaves the ACL-observation persistence strategy to the host.
    """

    source = CompanySource(initial_documents())
    brain = CompanyBrain()
    _sync_full(brain, source)
    current = brain.active["policy/security"]

    acl_only = company_document(
        "policy/security",
        current.body,
        current.revision,
        visibility="restricted",
        principals=(Principal(kind="group", identifier="security"),),
    )
    plan = plan_sync(
        brain.sync_state,
        source.incremental_page(cursor="cursor:acl", upserts=(acl_only,)),
        source_id=brain.source_id,
        mode=SyncMode.INCREMENTAL,
    )

    assert _document_ids(plan.upserts) == [current.document_id]
    assert plan.upserts[0].revision == current.revision

    with pytest.raises(ValueError, match="document revision already exists"):
        brain.apply(plan, mode=SyncMode.INCREMENTAL, label="acl_only")

    assert brain.store.get(SOURCE_ID, "policy/security", scope=brain.scope) == current


def test_stream_sync_rejects_a_page_after_the_terminal_page() -> None:
    source = CompanySource(initial_documents())
    pages = source.full_pages(2)
    terminal_first = [
        PollPage(upserts=pages[0].upserts, next_cursor="done", snapshot_complete=True),
        PollPage(upserts=pages[1].upserts, snapshot_complete=True),
    ]

    with pytest.raises(ValueError, match="after its terminal page"):
        list(
            stream_sync(
                terminal_first,
                CompanyBrain().sync_state,
                source_id=SOURCE_ID,
                mode=SyncMode.FULL,
            )
        )


def test_run_exercises_all_cycles_and_returns_json_serializable_results() -> None:
    result = run()

    json.dumps(result)  # the contract requires a JSON-serializable payload

    assert result["snapshot_deletes"] == []
    assert result["snapshot_cursor_held_until_complete"] is True
    assert result["snapshot_upserts"] == [
        canonical_document_id(SOURCE_ID, external_id)
        for external_id in (
            "policy/access",
            "policy/onboarding",
            "policy/payroll",
            "policy/refunds",
            "policy/security",
        )
    ]
    assert result["incremental_deletes"] == [
        canonical_document_id(SOURCE_ID, "policy/payroll")
    ]
    assert result["payroll_tombstone"] == {
        "removed_from_active": True,
        "removed_from_manifest": True,
        "revision_history_length": 1,
    }
    assert result["incremental_resume_rejected"] == (
        "incomplete full sync cannot resume as incremental"
    )
    assert result["interrupted_cursor_held"] is True
    assert result["reconcile_deletes"] == [
        canonical_document_id(SOURCE_ID, "policy/access")
    ]
    assert result["reconcile_reasons"] == ["absent_from_complete_snapshot"]
    assert result["generation_conflict"]["competing_error"] == (
        "sync generation mismatch: expected 6, found 7"
    )
    assert result["generation_conflict"]["competing_document_pending"] is True
    assert result["recovery_upserts"] == [
        canonical_document_id(SOURCE_ID, "policy/travel")
    ]
    assert result["replay_upserts"] == []
    assert result["replay_deletes"] == []
    assert result["generations_strictly_increasing"] is True
    assert result["active_external_ids"] == [
        "policy/benefits",
        "policy/onboarding",
        "policy/refunds",
        "policy/security",
        "policy/travel",
    ]
    assert result["manifest_document_ids"] == result["active_document_ids"]
