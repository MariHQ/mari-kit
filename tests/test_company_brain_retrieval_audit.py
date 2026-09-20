"""Adversarial audit of revision-aware authorization retrieval.

These tests probe the ref-keyed BM25 adapters and the revision-delta path for
authorization filtering, empty allowlists, stale revisions, updates, deletion,
and deterministic ranking. They are intentionally written against the public
API only.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from mari_kit.knowledge.artifacts import ArtifactRef
from mari_kit.references import ObjectRef, RevisionRef, ScopeRef
from mari_kit.retrieval import (
    ArtifactBM25Index,
    ArtifactIndexDelta,
    BM25Index,
    HNSWIndex,
    IndexDelta,
    IndexOperation,
    RevisionBM25Index,
)

SCOPE = ScopeRef(tenant="acme", space="handbook")


def artifact(artifact_id: str, revision: str, *, unit_id: str = "") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        revision=revision,
        unit_id=unit_id,
        namespace="handbook",
        scope=SCOPE,
    )


def revision(object_id: str, revision: str, *, unit_id: str = "") -> RevisionRef:
    return RevisionRef(
        object=ObjectRef(namespace="handbook", object_id=object_id, scope=SCOPE),
        revision=revision,
        unit_id=unit_id,
    )


def artifact_units(
    count: int, text: str = "shared retention clause"
) -> dict[ArtifactRef, str]:
    return {artifact(f"policy{i:02d}", "1"): text for i in range(count)}


def revision_units(
    count: int, text: str = "shared retention clause"
) -> dict[RevisionRef, str]:
    return {revision(f"policy{i:02d}", "1"): text for i in range(count)}


# --- authorization filtering -------------------------------------------------


def test_artifact_index_returns_only_authorized_revisions() -> None:
    old = artifact("clause", "1")
    current = artifact("clause", "2")
    index = ArtifactBM25Index({old: "old retention", current: "current retention"})

    assert [hit.ref for hit in index.search("retention", limit=5)] == [old, current]
    assert [
        hit.ref for hit in index.search("retention", limit=5, allowed_refs={old})
    ] == [old]
    assert [
        hit.ref for hit in index.search("retention", limit=5, allowed_refs={current})
    ] == [current]


def test_empty_allowlist_never_returns_hits() -> None:
    index = ArtifactBM25Index({artifact("clause", "1"): "retention clause"})
    assert index.search("retention", limit=5, allowed_refs=set()) == ()

    revisions = RevisionBM25Index({revision("clause", "1"): "retention clause"})
    assert revisions.search("retention", limit=5, allowed_refs=set()) == ()


def test_unknown_authorized_ref_is_ignored_without_error() -> None:
    present = artifact("clause", "1")
    index = ArtifactBM25Index({present: "retention clause"})
    absent = artifact("clause", "9")

    assert index.search("retention", limit=5, allowed_refs={absent}) == ()
    assert (
        index.search("retention", limit=5, allowed_refs={absent, present})[0].ref
        == present
    )


def test_revision_identity_is_not_interchangeable() -> None:
    first = revision("policy", "1")
    second = revision("policy", "2")
    moved = revision("policy", "1", unit_id="other")
    index = RevisionBM25Index({first: "retention clause", second: "retention clause"})

    assert index.search("retention", limit=5, allowed_refs={second})[0].ref == second
    assert index.search("retention", limit=5, allowed_refs={moved}) == ()
    assert index.explain("retention", ref=first).ref == first
    with pytest.raises(KeyError):
        index.explain("retention", ref=moved)


def test_hnsw_authorization_never_returns_disallowed_ids() -> None:
    index = HNSWIndex({"a": [1.0, 0.0], "b": [0.0, 1.0], "c": [1.0, 1.0]}, m=2)
    hits = index.search([1.0, 0.0], limit=5, ef_search=5, allowed_document_ids={"b"})
    assert {hit.document_id for hit in hits} <= {"b"}
    assert (
        index.search([1.0, 0.0], limit=5, ef_search=5, allowed_document_ids=set()) == ()
    )


# --- stale revisions, updates, deletion --------------------------------------


def test_replacement_of_absent_previous_revision_is_rejected() -> None:
    old = artifact("runbook", "1")
    index = ArtifactBM25Index({old: "restart service"})

    with pytest.raises(ValueError, match="expected artifact revision is absent"):
        index.with_deltas(
            (
                ArtifactIndexDelta(
                    ref=artifact("runbook", "3"),
                    previous_ref=artifact("runbook", "2"),
                    operation=IndexOperation.UPSERT,
                    text="drain queue",
                ),
            )
        )
    assert index.search("restart", limit=1)[0].ref == old


def test_artifact_update_and_delete_are_immutable_and_authorization_aware() -> None:
    old = artifact("runbook", "1")
    current = artifact("runbook", "2")
    original = ArtifactBM25Index({old: "restart service"})

    updated = original.with_deltas(
        (
            ArtifactIndexDelta(
                ref=current,
                previous_ref=old,
                operation=IndexOperation.UPSERT,
                text="shed retries",
            ),
        )
    )
    assert original.search("restart", limit=5)[0].ref == old
    assert old not in {hit.ref for hit in updated.search("restart", limit=5)}
    assert updated.search("shed", limit=5)[0].ref == current
    assert updated.search("shed", limit=5, allowed_refs={old}) == ()
    assert updated.search("shed", limit=5, allowed_refs={current})[0].ref == current

    deleted = updated.with_deltas(
        (ArtifactIndexDelta(ref=current, operation=IndexOperation.DELETE),)
    )
    assert deleted.search("shed", limit=5) == ()
    assert updated.search("shed", limit=5)[0].ref == current


def test_delete_of_absent_artifact_revision_is_rejected() -> None:
    index = ArtifactBM25Index({artifact("runbook", "1"): "restart service"})
    with pytest.raises(ValueError, match="artifact revision is absent"):
        index.with_deltas(
            (
                ArtifactIndexDelta(
                    ref=artifact("runbook", "9"),
                    operation=IndexOperation.DELETE,
                ),
            )
        )


def test_bm25_expected_revision_guard_and_delete_to_empty() -> None:
    index = BM25Index({"policy": "retention clause"}, revisions={"policy": "1"})
    updated = index.with_deltas(
        (
            IndexDelta(
                item_id="policy",
                operation=IndexOperation.UPSERT,
                text="retention clause revised",
                revision="2",
                expected_revision="1",
            ),
        )
    )
    assert index.revisions["policy"] == "1"
    assert updated.revisions["policy"] == "2"

    with pytest.raises(ValueError, match="revision mismatch"):
        updated.with_deltas(
            (
                IndexDelta(
                    item_id="policy",
                    operation=IndexOperation.DELETE,
                    expected_revision="1",
                ),
            )
        )

    emptied = updated.with_deltas(
        (
            IndexDelta(
                item_id="policy",
                operation=IndexOperation.DELETE,
                expected_revision="2",
            ),
        )
    )
    assert emptied.search("retention", limit=5) == ()
    assert emptied.revisions == {}
    assert emptied.documents == {}


def test_artifact_index_delta_rejects_cross_unit_replacement() -> None:
    with pytest.raises(ValueError, match="same artifact unit"):
        ArtifactIndexDelta(
            ref=artifact("runbook", "2"),
            previous_ref=artifact("other", "1"),
            operation=IndexOperation.UPSERT,
            text="shed retries",
        )
    with pytest.raises(ValueError, match="require text"):
        ArtifactIndexDelta(
            ref=artifact("runbook", "2"),
            operation=IndexOperation.UPSERT,
            text="   ",
        )
    with pytest.raises(ValueError, match="do not accept previous_ref"):
        ArtifactIndexDelta(
            ref=artifact("runbook", "2"),
            previous_ref=artifact("runbook", "1"),
            operation=IndexOperation.DELETE,
        )


# --- deterministic ranking ---------------------------------------------------


def test_ref_keyed_tie_break_follows_structural_order_past_ten_units() -> None:
    # Regression: unpadded synthetic positions made "10" sort before "02", so a
    # truncating limit dropped an earlier structural unit for a later one.
    artifacts = artifact_units(12)
    artifact_index = ArtifactBM25Index(artifacts)
    assert [
        hit.ref.artifact_id for hit in artifact_index.search("shared", limit=3)
    ] == ["policy00", "policy01", "policy02"]
    assert [
        hit.ref.artifact_id for hit in artifact_index.search("shared", limit=12)
    ] == [f"policy{index:02d}" for index in range(12)]

    revisions = revision_units(12)
    revision_index = RevisionBM25Index(revisions)
    assert [
        hit.ref.object.object_id for hit in revision_index.search("shared", limit=3)
    ] == ["policy00", "policy01", "policy02"]
    assert [
        hit.ref.object.object_id for hit in revision_index.search("shared", limit=12)
    ] == [f"policy{index:02d}" for index in range(12)]


def test_ref_keyed_ranking_is_independent_of_construction_order() -> None:
    items = [
        (artifact("policy02", "1"), "shared token"),
        (artifact("policy00", "1"), "shared token"),
        (artifact("policy01", "1"), "shared token"),
    ]
    baseline = [
        hit.ref.artifact_id
        for hit in ArtifactBM25Index(dict(items)).search("shared", limit=3)
    ]
    assert baseline == ["policy00", "policy01", "policy02"]

    for position in range(len(items)):
        reordered: Mapping[ArtifactRef, str] = dict(items[position:] + items[:position])
        assert [
            hit.ref.artifact_id
            for hit in ArtifactBM25Index(reordered).search("shared", limit=3)
        ] == baseline


def test_ranking_is_repeatable_and_scope_partitions_do_not_mix() -> None:
    scope_a = ScopeRef(tenant="acme", space="a")
    scope_b = ScopeRef(tenant="acme", space="b")
    a = ArtifactRef(artifact_id="policy", revision="1", namespace="n", scope=scope_a)
    b = ArtifactRef(artifact_id="policy", revision="1", namespace="n", scope=scope_b)
    index = ArtifactBM25Index({a: "retention clause", b: "retention settings"})

    first = tuple((hit.ref, hit.score) for hit in index.search("retention", limit=5))
    for _ in range(5):
        assert (
            tuple((hit.ref, hit.score) for hit in index.search("retention", limit=5))
            == first
        )
    assert [
        hit.ref for hit in index.search("retention", limit=5, allowed_refs={a})
    ] == [a]
    assert [
        hit.ref for hit in index.search("retention", limit=5, allowed_refs={b})
    ] == [b]
