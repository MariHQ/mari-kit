"""Adversarial audit coverage for the company-brain synchronization planner.

These tests probe the guarantees in ``mari_kit.sync.planning`` from a host that
ships a continuously synchronized company brain:

* crash/retry recovery is replay-safe and generation-guarded,
* an incomplete full snapshot never reconciles absence,
* explicit tombstones are authoritative in either mode,
* contradictory pages are rejected,
* every content- and ACL-bearing field participates in fingerprinting,
* sync state stays source- and configuration-bound,
* every plan advances exactly one generation.

The tests are intentionally independent of ``tests/test_sync.py`` and exercise
edge cases that the shipped suite does not: interrupted-then-resumed full
snapshots, resurrection after an in-snapshot tombstone, encoded external IDs,
stale-plan rejection without side effects, and fingerprint stability.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from mari_kit import (
    DocumentACL,
    KnowledgeDocument,
    PollPage,
    Principal,
    SyncMode,
    Tombstone,
    canonical_document_id,
)
from mari_kit.sync import (
    ManifestEntry,
    SyncPlan,
    SyncState,
    apply_sync_plan,
    document_fingerprint,
    plan_sync,
    stream_sync,
)

SOURCE = "handbook:acme"


def document(
    external_id: str,
    *,
    revision: str = "r1",
    body: str | None = None,
    title: str | None = None,
    provider_revision: str = "",
    updated_at: str = "",
    source_url: str = "",
    acl: DocumentACL | None = None,
    metadata: dict[str, object] | None = None,
    source_id: str = SOURCE,
) -> KnowledgeDocument:
    return KnowledgeDocument(
        source_id=source_id,
        external_id=external_id,
        title=title if title is not None else external_id,
        body=body if body is not None else f"body of {external_id}",
        revision=revision,
        provider_revision=provider_revision,
        updated_at=updated_at,
        source_url=source_url,
        acl=acl if acl is not None else DocumentACL(),
        metadata=metadata if metadata is not None else {},
    )


def entry(
    external_id: str, fingerprint: str = "stale", *, source_id: str = SOURCE
) -> ManifestEntry:
    return ManifestEntry(
        fingerprint=fingerprint,
        revision="r1",
        source_id=source_id,
        external_id=external_id,
    )


def plan(
    state: SyncState,
    page: PollPage,
    *,
    mode: SyncMode = SyncMode.INCREMENTAL,
    configuration_fingerprint: str = "",
) -> SyncPlan:
    return plan_sync(
        state,
        page,
        source_id=SOURCE,
        mode=mode,
        configuration_fingerprint=configuration_fingerprint,
    )


@dataclass
class RecordingTransaction:
    """Host-owned staged transaction used to prove ordering and safety."""

    generation: int = 0
    ops: list[tuple[str, str]] = field(default_factory=list)
    committed_state: SyncState | None = None

    def upsert(self, document: KnowledgeDocument) -> None:
        self.ops.append(("upsert", document.document_id))

    def delete(self, tombstone: Tombstone) -> None:
        self.ops.append(("delete", tombstone.document_id))

    def commit(self, state: SyncState) -> None:
        self.committed_state = state
        self.ops.append(("commit", state.source_id))


# ---------------------------------------------------------------------------
# Crash/retry recovery
# ---------------------------------------------------------------------------


def test_replanning_the_same_page_from_the_same_state_is_deterministic() -> None:
    state = SyncState(
        source_id=SOURCE,
        manifest={canonical_document_id(SOURCE, "kept"): entry("kept")},
    )
    page = PollPage(
        upserts=(document("kept"), document("added")),
        tombstones=(Tombstone(source_id=SOURCE, external_id="gone"),),
        next_checkpoint="page-2",
    )

    first = plan(state, page, mode=SyncMode.FULL)
    second = plan(state, page, mode=SyncMode.FULL)

    assert first.upserts == second.upserts
    assert first.deletes == second.deletes
    assert first.unchanged == second.unchanged
    assert first.state == second.state


def test_interrupted_full_snapshot_resumes_without_reconciling_absence() -> None:
    state = SyncState(
        source_id=SOURCE,
        cursor="durable",
        manifest={
            canonical_document_id(SOURCE, "a"): entry("a"),
            canonical_document_id(SOURCE, "b"): entry("b"),
            canonical_document_id(SOURCE, "c"): entry("c"),
        },
    )

    first = plan(
        state,
        PollPage(upserts=(document("a"),), next_checkpoint="p2"),
        mode=SyncMode.FULL,
    )
    assert first.deletes == ()
    assert first.state.cursor == "durable"
    assert first.state.checkpoint == "p2"
    assert first.state.active_mode is SyncMode.FULL
    assert first.state.full_seen == frozenset({canonical_document_id(SOURCE, "a")})

    # A crash before commit replays the same page against the same durable state.
    replay = plan(
        state,
        PollPage(upserts=(document("a"),), next_checkpoint="p2"),
        mode=SyncMode.FULL,
    )
    assert replay.state.full_seen == first.state.full_seen

    # Resuming from the persisted checkpoint keeps the accumulated seen set.
    resumed = plan(
        first.state,
        PollPage(upserts=(document("b"),), next_checkpoint="p3"),
        mode=SyncMode.FULL,
    )
    terminal = plan(
        resumed.state,
        PollPage(upserts=(document("c"),), next_cursor="next", snapshot_complete=True),
        mode=SyncMode.FULL,
    )
    assert terminal.deletes == ()
    assert terminal.state.active_mode is None
    assert terminal.state.full_seen == frozenset()
    assert set(terminal.state.manifest) == {
        canonical_document_id(SOURCE, value) for value in ("a", "b", "c")
    }


def test_full_snapshot_deletes_a_document_missing_after_resume() -> None:
    state = SyncState(
        source_id=SOURCE,
        manifest={
            canonical_document_id(SOURCE, "a"): entry("a"),
            canonical_document_id(SOURCE, "b"): entry("b"),
        },
    )
    first = plan(
        state,
        PollPage(upserts=(document("a"),), next_checkpoint="p2"),
        mode=SyncMode.FULL,
    )
    terminal = plan(
        first.state,
        PollPage(next_cursor="done", snapshot_complete=True),
        mode=SyncMode.FULL,
    )
    assert [(item.document_id, item.reason) for item in terminal.deletes] == [
        (canonical_document_id(SOURCE, "b"), "absent_from_complete_snapshot")
    ]


def test_stale_plan_is_rejected_before_any_transaction_side_effect() -> None:
    base = SyncState(source_id=SOURCE)
    accepted = plan(
        base,
        PollPage(upserts=(document("a"),), next_cursor="c1", snapshot_complete=True),
    )
    competing = plan(
        base,
        PollPage(upserts=(document("b"),), next_cursor="c2", snapshot_complete=True),
    )
    assert accepted.expected_generation == competing.expected_generation == 0

    transaction = RecordingTransaction(generation=0)
    apply_sync_plan(accepted, transaction=transaction)
    assert transaction.ops == [
        ("upsert", canonical_document_id(SOURCE, "a")),
        ("commit", SOURCE),
    ]
    durable = transaction.committed_state
    assert durable is not None

    # The host reloads its durable state at generation 1; the competing plan
    # still claims generation 0 and must be rejected before any side effect.
    stale = RecordingTransaction(generation=durable.generation)
    with pytest.raises(ValueError, match="generation mismatch"):
        apply_sync_plan(competing, transaction=stale)
    assert stale.ops == []
    assert stale.committed_state is None


# ---------------------------------------------------------------------------
# Incomplete full snapshots
# ---------------------------------------------------------------------------


def test_incomplete_full_page_never_deletes_even_with_stale_manifest() -> None:
    state = SyncState(
        source_id=SOURCE,
        manifest={canonical_document_id(SOURCE, "stale"): entry("stale")},
    )
    plan_result = plan(state, PollPage(next_checkpoint="p2"), mode=SyncMode.FULL)
    assert plan_result.deletes == ()
    assert plan_result.snapshot_complete is False
    assert plan_result.warnings
    assert canonical_document_id(SOURCE, "stale") in plan_result.state.manifest


def test_incomplete_full_snapshot_is_mode_locked_both_directions() -> None:
    full = plan(SyncState(), PollPage(next_checkpoint="p2"), mode=SyncMode.FULL)
    with pytest.raises(ValueError, match="cannot resume"):
        plan(full.state, PollPage(snapshot_complete=True), mode=SyncMode.INCREMENTAL)

    incremental = plan(
        SyncState(), PollPage(next_checkpoint="p2"), mode=SyncMode.INCREMENTAL
    )
    with pytest.raises(ValueError, match="cannot resume"):
        plan(incremental.state, PollPage(snapshot_complete=True), mode=SyncMode.FULL)


def test_incomplete_page_cannot_advance_the_durable_cursor() -> None:
    state = SyncState(source_id=SOURCE, cursor="durable", checkpoint="old")
    plan_result = plan(
        state,
        PollPage(next_cursor="advanced-too-far", next_checkpoint="p2"),
        mode=SyncMode.FULL,
    )
    assert plan_result.state.cursor == "durable"
    assert plan_result.state.checkpoint == "p2"


def test_full_seen_stays_a_subset_of_the_manifest_while_incomplete() -> None:
    state = SyncState(source_id=SOURCE)
    final: SyncState | None = None
    for external in ("a", "b", "c"):
        step = plan(
            state,
            PollPage(upserts=(document(external),), next_checkpoint=f"p-{external}"),
            mode=SyncMode.FULL,
        )
        state = step.state
        assert state.full_seen <= set(state.manifest)
        assert state.active_mode is SyncMode.FULL
        final = state
    assert final is not None

    tombstoned = plan(
        final,
        PollPage(tombstones=(Tombstone(source_id=SOURCE, external_id="b"),)),
        mode=SyncMode.FULL,
    )
    assert canonical_document_id(SOURCE, "b") not in tombstoned.state.full_seen
    assert tombstoned.state.full_seen <= set(tombstoned.state.manifest)


def test_replaying_a_terminal_full_snapshot_is_a_noop() -> None:
    first = plan(
        SyncState(),
        PollPage(upserts=(document("a"),), next_cursor="done", snapshot_complete=True),
        mode=SyncMode.FULL,
    )
    replay = plan(
        first.state,
        PollPage(upserts=(document("a"),), next_cursor="done", snapshot_complete=True),
        mode=SyncMode.FULL,
    )
    assert replay.upserts == ()
    assert replay.deletes == ()
    assert replay.unchanged == (canonical_document_id(SOURCE, "a"),)


# ---------------------------------------------------------------------------
# Tombstones
# ---------------------------------------------------------------------------


def test_explicit_tombstone_is_authoritative_in_incomplete_incremental_page() -> None:
    state = SyncState(
        source_id=SOURCE,
        cursor="cursor",
        manifest={canonical_document_id(SOURCE, "gone"): entry("gone")},
    )
    plan_result = plan(
        state,
        PollPage(
            tombstones=(Tombstone(source_id=SOURCE, external_id="gone"),),
            next_checkpoint="p2",
        ),
        mode=SyncMode.INCREMENTAL,
    )
    assert [(item.document_id, item.reason) for item in plan_result.deletes] == [
        (canonical_document_id(SOURCE, "gone"), "provider_deleted")
    ]
    assert canonical_document_id(SOURCE, "gone") not in plan_result.state.manifest
    assert plan_result.state.cursor == "cursor"


def test_document_tombstoned_then_reupserted_in_one_full_snapshot_survives() -> None:
    state = SyncState(
        source_id=SOURCE,
        manifest={canonical_document_id(SOURCE, "a"): entry("a")},
    )
    tombstoned = plan(
        state,
        PollPage(
            tombstones=(Tombstone(source_id=SOURCE, external_id="a"),),
            next_checkpoint="p2",
        ),
        mode=SyncMode.FULL,
    )
    assert len(tombstoned.deletes) == 1

    terminal = plan(
        tombstoned.state,
        PollPage(
            upserts=(document("a", revision="r2"),),
            next_cursor="done",
            snapshot_complete=True,
        ),
        mode=SyncMode.FULL,
    )
    assert terminal.deletes == ()
    assert canonical_document_id(SOURCE, "a") in terminal.state.manifest


def test_absence_tombstone_preserves_encoded_external_identity() -> None:
    external = "policy/refunds:2026"
    document_id = canonical_document_id(SOURCE, external)
    state = SyncState(source_id=SOURCE, manifest={document_id: entry(external)})

    terminal = plan(
        state, PollPage(next_cursor="done", snapshot_complete=True), mode=SyncMode.FULL
    )

    assert len(terminal.deletes) == 1
    tombstone = terminal.deletes[0]
    assert tombstone.source_id == SOURCE
    assert tombstone.external_id == external
    assert tombstone.document_id == document_id


# ---------------------------------------------------------------------------
# Contradictory pages
# ---------------------------------------------------------------------------


def test_duplicate_upserts_and_tombstones_are_rejected() -> None:
    duplicate = document("a")
    with pytest.raises(ValueError, match="duplicate document IDs"):
        plan(SyncState(), PollPage(upserts=(duplicate, duplicate)))

    tombstone = Tombstone(source_id=SOURCE, external_id="a")
    with pytest.raises(ValueError, match="duplicate tombstones"):
        plan(SyncState(), PollPage(tombstones=(tombstone, tombstone)))


def test_upsert_and_tombstone_for_same_document_are_rejected() -> None:
    with pytest.raises(ValueError, match="both upserts and deletes"):
        plan(
            SyncState(),
            PollPage(
                upserts=(document("a"),),
                tombstones=(Tombstone(source_id=SOURCE, external_id="a"),),
            ),
        )


# ---------------------------------------------------------------------------
# Fingerprint changes
# ---------------------------------------------------------------------------


def test_every_content_and_acl_field_changes_the_fingerprint() -> None:
    baseline_kwargs: dict[str, object] = {
        "external_id": "a",
        "revision": "r1",
        "body": "body",
        "title": "Title",
        "provider_revision": "provider-1",
        "updated_at": "2026-01-01T00:00:00Z",
        "source_url": "https://example.test/a",
        "acl": DocumentACL(
            visibility="restricted",
            principals=(Principal(kind="group", identifier="eng"),),
        ),
        "metadata": {"tag": "one"},
    }
    fingerprint = document_fingerprint(document(**baseline_kwargs))  # type: ignore[arg-type]

    overrides: dict[str, dict[str, object]] = {
        "revision": {"revision": "r2"},
        "body": {"body": "changed"},
        "title": {"title": "Other"},
        "provider_revision": {"provider_revision": "provider-2"},
        "updated_at": {"updated_at": "2026-02-01T00:00:00Z"},
        "source_url": {"source_url": "https://example.test/b"},
        "acl.visibility": {"acl": DocumentACL(visibility="public")},
        "acl.principals": {
            "acl": DocumentACL(
                visibility="restricted",
                principals=(Principal(kind="group", identifier="other"),),
            )
        },
        "metadata": {"metadata": {"tag": "two"}},
    }
    for name, override in overrides.items():
        variant_kwargs = {**baseline_kwargs, **override}
        assert document_fingerprint(document(**variant_kwargs)) != fingerprint, name  # type: ignore[arg-type]


def test_metadata_cannot_mark_a_changed_document_as_unchanged() -> None:
    first = plan(
        SyncState(),
        PollPage(upserts=(document("a", body="original"),), snapshot_complete=True),
    )
    changed = document("a", body="changed", metadata={"unchanged": True})
    second = plan(first.state, PollPage(upserts=(changed,), snapshot_complete=True))
    assert second.upserts == (changed,)
    assert second.unchanged == ()


def test_fingerprint_ignores_mapping_order_but_not_identity() -> None:
    left = document("a", metadata={"b": 2, "a": 1})
    right = document("a", metadata={"a": 1, "b": 2})
    other = document("a", revision="r2", metadata={"a": 1, "b": 2})
    assert document_fingerprint(left) == document_fingerprint(right)
    assert document_fingerprint(left) != document_fingerprint(other)


# ---------------------------------------------------------------------------
# Source binding
# ---------------------------------------------------------------------------


def test_state_binds_to_first_source_and_rejects_another() -> None:
    bound = plan(SyncState(), PollPage(snapshot_complete=True)).state

    with pytest.raises(ValueError, match="belongs to"):
        plan_sync(
            bound,
            PollPage(snapshot_complete=True),
            source_id="other:source",
            mode=SyncMode.INCREMENTAL,
        )


def test_pages_with_foreign_documents_or_tombstones_are_rejected() -> None:
    with pytest.raises(ValueError, match="foreign sources"):
        plan(
            SyncState(),
            PollPage(upserts=(document("a", source_id="other"),)),
        )
    with pytest.raises(ValueError, match="foreign sources"):
        plan(
            SyncState(),
            PollPage(tombstones=(Tombstone(source_id="other", external_id="a"),)),
        )


def test_configuration_fingerprint_binds_on_first_plan_and_rejects_drift() -> None:
    bound = plan(
        SyncState(),
        PollPage(snapshot_complete=True),
        configuration_fingerprint="scope-a",
    ).state
    assert bound.configuration_fingerprint == "scope-a"

    with pytest.raises(ValueError, match="configuration changed"):
        plan(
            bound, PollPage(snapshot_complete=True), configuration_fingerprint="scope-b"
        )
    with pytest.raises(ValueError, match="configuration changed"):
        plan(bound, PollPage(snapshot_complete=True))

    # The same fingerprint (including surrounding whitespace) is accepted.
    assert (
        plan(
            bound,
            PollPage(snapshot_complete=True),
            configuration_fingerprint=" scope-a ",
        ).state.configuration_fingerprint
        == "scope-a"
    )


# ---------------------------------------------------------------------------
# Generation safety
# ---------------------------------------------------------------------------


def test_every_plan_advances_exactly_one_generation_including_noops() -> None:
    state = SyncState(source_id=SOURCE)
    for expected in range(4):
        step = plan(state, PollPage(next_checkpoint=f"p{expected}"), mode=SyncMode.FULL)
        assert step.expected_generation == expected
        assert step.state.generation == expected + 1
        state = step.state


def test_stream_sync_chains_generations_and_stops_after_terminal_page() -> None:
    pages = [
        PollPage(upserts=(document("a"),), next_checkpoint="p2"),
        PollPage(upserts=(document("b"),), next_cursor="done", snapshot_complete=True),
    ]
    plans = list(stream_sync(pages, SyncState(), source_id=SOURCE, mode=SyncMode.FULL))

    assert [step.expected_generation for step in plans] == [0, 1]
    assert [step.state.generation for step in plans] == [1, 2]
    assert plans[-1].state.active_mode is None
    assert set(plans[-1].state.manifest) == {
        canonical_document_id(SOURCE, "a"),
        canonical_document_id(SOURCE, "b"),
    }

    with pytest.raises(ValueError, match="after its terminal page"):
        list(
            stream_sync(
                [*pages, PollPage(snapshot_complete=True)],
                SyncState(),
                source_id=SOURCE,
                mode=SyncMode.FULL,
            )
        )


def test_stream_sync_rejects_an_empty_page_iterable() -> None:
    with pytest.raises(ValueError, match="no polling pages"):
        list(stream_sync((), SyncState(), source_id=SOURCE, mode=SyncMode.INCREMENTAL))


def test_apply_sync_plan_applies_upserts_then_deletes_then_commits() -> None:
    state = SyncState(source_id=SOURCE)
    step = plan(
        state,
        PollPage(
            upserts=(document("a"),),
            tombstones=(Tombstone(source_id=SOURCE, external_id="b"),),
            next_cursor="done",
            snapshot_complete=True,
        ),
    )
    transaction = RecordingTransaction(generation=0)
    apply_sync_plan(step, transaction=transaction)

    assert transaction.ops == [
        ("upsert", canonical_document_id(SOURCE, "a")),
        ("delete", canonical_document_id(SOURCE, "b")),
        ("commit", SOURCE),
    ]
    assert transaction.committed_state == step.state
