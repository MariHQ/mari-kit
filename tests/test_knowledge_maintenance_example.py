from dataclasses import replace

import pytest

from examples.quickstarts.knowledge_maintenance import Maintenance, messages


def test_complete_event_sequence_and_clean_rebuild_equivalence():
    host = Maintenance()
    rows = messages()
    assert host.refresh(rows, generation="1")["vectors_rebuilt"] == 2
    ids = tuple(g.object for g in host.previous_topics)
    assert host.refresh(rows, generation="2")["vectors_rebuilt"] == 0
    # Rebinding exact same text must not re-embed the topic text.
    rows = (replace(rows[0], revision="2"), rows[1])
    assert host.refresh(rows, generation="3")["vectors_rebuilt"] == 0
    assert tuple(g.object for g in host.previous_topics) == ids
    rows = (
        replace(rows[0], revision="3", text="Refunds close after 14 days."),
        rows[1],
    )
    assert host.refresh(rows, generation="4")["vectors_rebuilt"] == 1
    assert host.query("refunds")
    rows = (
        *rows,
        replace(
            rows[0],
            event_id="c",
            revision="1",
            timestamp=4000,
            text="Refunds require a receipt.",
        ),
    )
    assert host.refresh(rows, generation="5")["vectors_rebuilt"] == 1
    merged = host.refresh(rows, generation="6", merge_topics=True)
    assert merged["topics"] == 1 and merged["retired_topics"] == 1
    assert merged["topic_transitions"] == [("merged",)]
    split = host.refresh(rows, generation="7")
    assert split["topics"] == 2
    assert all("split" in t for t in split["topic_transitions"])
    assert (
        host.refresh(rows, generation="8", model="fixture:v2")["vectors_rebuilt"] == 2
    )
    # Changed extraction recipe, same exact summary text: keep vectors.
    assert (
        host.refresh(rows, generation="9", model="fixture:v2", extraction="extract:v2")[
            "vectors_rebuilt"
        ]
        == 0
    )
    host.refresh(rows, generation="10", denied=frozenset({"a", "c"}))
    assert not host.query("refunds")
    assert host.count.value == 1
    assert host.lexical.value["documents"] == 1
    host.refresh((), generation="11")
    assert not host.query("refunds")
    assert host.count.value == 0
    assert host.centroid.value["count"] == 0
    assert host.membership.value == {}
    assert host.refresh((), generation="12")["vectors_rebuilt"] == 0


def test_failed_build_withholds_projection_and_retry_recovers():
    host = Maintenance()
    rows = messages()
    host.refresh(rows, generation="1")
    with pytest.raises(RuntimeError):
        host.refresh(rows, generation="2", model="fixture:v2", fail_aspect="vector")
    with pytest.raises(ValueError, match="unavailable"):
        host.query("refunds")
    host.refresh(rows, generation="2", model="fixture:v2")
    assert host.query("refunds")
    # Read-time access revocation must fail even if a snapshot was previously built.
    host.denied = frozenset({"a"})
    with pytest.raises(ValueError, match="unauthorized"):
        host.query("refunds")
