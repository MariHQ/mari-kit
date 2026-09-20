from dataclasses import replace

import pytest

from mari_kit import ObjectRef, RevisionRef, ScopeRef
from mari_kit.retrieval import IndexOperation, RevisionBM25Index, RevisionIndexDelta


def ref(tenant="acme", revision="1", unit="policy"):
    return RevisionRef(
        object=ObjectRef(
            namespace="handbook",
            object_id="refunds",
            scope=ScopeRef(tenant=tenant),
        ),
        revision=revision,
        unit_id=unit,
    )


def test_revision_deltas_match_rebuild_and_preserve_other_tenants():
    old, new, other = ref(), ref(revision="2"), ref(tenant="beta")
    initial = RevisionBM25Index({old: "refund thirty", other: "refund sixty"})
    updated = initial.with_deltas(
        [
            RevisionIndexDelta(
                ref=new,
                previous_ref=old,
                operation=IndexOperation.UPSERT,
                text="refund forty",
            )
        ]
    )
    rebuilt = RevisionBM25Index({new: "refund forty", other: "refund sixty"})
    assert updated.search("refund forty", limit=5) == rebuilt.search(
        "refund forty", limit=5
    )
    assert updated.search("refund", limit=5, allowed_refs={old}) == ()
    assert updated.search("refund", limit=5, allowed_refs=set()) == ()
    assert initial.search("refund", limit=5, allowed_refs={old})[0].ref == old
    deleted = updated.with_deltas(
        [RevisionIndexDelta(ref=new, operation=IndexOperation.DELETE)]
    )
    assert [hit.ref for hit in deleted.search("refund", limit=5)] == [other]


@pytest.mark.parametrize(
    "other",
    [
        ref(tenant="beta"),
        ref(unit="another-section"),
        replace(ref(), object=ObjectRef(namespace="other", object_id="refunds")),
    ],
)
def test_revision_replacement_cannot_cross_object_or_unit(other):
    with pytest.raises(ValueError, match="same.*unit"):
        RevisionIndexDelta(
            ref=other,
            previous_ref=ref(),
            operation=IndexOperation.UPSERT,
            text="new policy",
        )


def test_failed_revision_batch_leaves_original_snapshot_unchanged():
    old, new = ref(), ref(revision="2")
    initial = RevisionBM25Index({old: "refund thirty"})
    with pytest.raises(ValueError, match="absent"):
        initial.with_deltas(
            [
                RevisionIndexDelta(
                    ref=new,
                    previous_ref=old,
                    operation=IndexOperation.UPSERT,
                    text="refund forty",
                ),
                RevisionIndexDelta(ref=old, operation=IndexOperation.DELETE),
            ]
        )
    assert initial.search("refund", limit=5)[0].ref == old


def test_revision_updates_preserve_custom_analyzer_and_scoring_parameters():
    def analyzer(text):
        return text.split("|")

    old, new = ref(), ref(revision="2")
    initial = RevisionBM25Index({old: "A|B"}, k1=2.0, b=0.1, analyzer=analyzer)
    updated = initial.with_deltas(
        [
            RevisionIndexDelta(
                ref=new, previous_ref=old, operation=IndexOperation.UPSERT, text="C|D|D"
            )
        ]
    )
    rebuilt = RevisionBM25Index({new: "C|D|D"}, k1=2.0, b=0.1, analyzer=analyzer)
    assert updated.explain("D", ref=new) == rebuilt.explain("D", ref=new)
    assert updated.explain("d", ref=new).score == 0
    empty = updated.with_deltas(
        [RevisionIndexDelta(ref=new, operation=IndexOperation.DELETE)]
    )
    assert empty.search("D", limit=5) == ()


def test_revision_delta_rejects_invalid_payloads_and_stale_replacement():
    with pytest.raises(ValueError, match="text"):
        RevisionIndexDelta(ref=ref(), operation=IndexOperation.UPSERT, text=" ")
    with pytest.raises(ValueError, match="previous_ref"):
        RevisionIndexDelta(
            ref=ref(), previous_ref=ref(), operation=IndexOperation.DELETE
        )
    with pytest.raises(ValueError, match="absent"):
        RevisionBM25Index({ref(revision="2"): "refund"}).with_deltas(
            [
                RevisionIndexDelta(
                    ref=ref(revision="3"),
                    previous_ref=ref(),
                    operation=IndexOperation.UPSERT,
                    text="changed",
                )
            ]
        )
