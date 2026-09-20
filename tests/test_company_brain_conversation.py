"""Behavioral tests for the conversation-derived company brain example."""

from __future__ import annotations

import copy
import json

import pytest

from examples.company_brains import conversation as brain
from mari_kit.conversation_knowledge import (
    compile_episodes,
    evidence_context,
    extraction_request,
    merge_chunk_knowledge,
    parse_episode_knowledge,
    resolve_evidence,
    segment_conversations,
    split_for_output,
    topic_history,
)
from mari_kit.errors import MalformedModelOutput


def _compile_initial():
    events = brain.initial_events()
    episodes = segment_conversations(events)
    result = compile_episodes(
        episodes, generate=brain.fixture, cache={}, now=brain.NOW, resolve=True
    )
    return events, episodes, result


def _by_title(artifacts, title):
    return next(artifact for artifact in artifacts if artifact.title == title)


def test_run_returns_json_serializable_company_brain():
    report = brain.run()
    assert json.loads(json.dumps(report)) == report
    assert report["extraction"]["episode_count"] == 4
    assert {episode["title"] for episode in report["episodes"]} == {
        "Enterprise refund window",
        "Checkout retry-storm failure",
        "Batch scheduler migration",
        "Checkout failover region",
    }


def test_claims_are_bound_to_exact_source_spans():
    report = brain.run()
    sources = {event.event_id: event for event in brain.edited_events()}
    for episode in report["episodes"]:
        for claim in episode["claims"]:
            assert claim["evidence"]
            for span in claim["evidence"]:
                source = sources[span["event_id"]]
                assert span["revision"] == source.revision
                assert source.text[span["start"] : span["end"]] == span["quote"]


def test_extraction_reports_resolved_and_dropped_claims():
    report = brain.run()
    assert report["extraction"]["first_calls"] == 4
    assert report["extraction"]["dropped"] == [
        {
            "reason": "quote-not-found",
            "text": "Refunds are settled in five business days.",
        }
    ]


def test_cache_reuses_unchanged_episodes_and_recompiles_edits():
    report = brain.run()
    assert report["cache"] == {
        "second_calls": 0,
        "second_reused": 4,
        "after_edit_calls": 1,
        "after_edit_reused": 3,
    }
    edits = report["edits"]
    assert edits["cache_key_changed"] is True
    assert edits["old_cache_key"] != edits["new_cache_key"]


def test_compile_episodes_reuse_is_revision_bound_and_never_calls_model():
    _, episodes, first = _compile_initial()
    cache = {artifact.cache_key: artifact for artifact in first.artifacts}
    calls: list[dict] = []

    def generate(request):
        calls.append(request)
        return brain.fixture(request)

    second = compile_episodes(
        episodes, generate=generate, cache=cache, now=brain.NOW, resolve=True
    )
    assert second.calls == 0
    assert second.reused == len(episodes)
    assert calls == []


def test_evidence_context_fails_closed_on_edit_delete_and_revocation():
    events, _, result = _compile_initial()
    refund = _by_title(result.artifacts, "Enterprise refund window")
    private = _by_title(result.artifacts, "Checkout failover region")
    allowed = brain.allowed_for([])

    rendered = evidence_context(refund, current_events=events, allowed=allowed)
    assert "Enterprise refunds should stay at 30 days" in rendered

    with pytest.raises(ValueError):
        evidence_context(refund, current_events=brain.edited_events(), allowed=allowed)
    with pytest.raises(ValueError):
        evidence_context(
            refund,
            current_events=[e for e in events if e.event_id != "r2"],
            allowed=allowed,
        )
    with pytest.raises(ValueError):
        evidence_context(private, current_events=events, allowed=allowed)
    evidence_context(private, current_events=events, allowed=brain.allowed_for(["sre"]))


def test_retrieval_fuses_facets_and_resolves_original_evidence():
    report = brain.run()
    hits = report["retrieval"]["refund_query"]
    assert len(hits) == 1
    assert hits[0]["title"] == "Enterprise refund window"
    assert hits[0]["unit_id"] == "questions"
    assert hits[0]["score"] > 0
    assert "30-day window" in hits[0]["evidence"]
    assert "finance already reports" in hits[0]["evidence"]


def test_retrieval_honors_authorization_at_episode_granularity():
    report = brain.run()
    restricted = next(
        episode
        for episode in report["episodes"]
        if episode["title"] == "Checkout failover region"
    )
    customer_hits = report["retrieval"]["failover_query_customer"]
    sre_hits = report["retrieval"]["failover_query_sre"]
    assert all(hit["episode_id"] != restricted["episode_id"] for hit in customer_hits)
    assert any(hit["episode_id"] == restricted["episode_id"] for hit in sre_hits)
    allowed_hit = next(
        hit for hit in sre_hits if hit["episode_id"] == restricted["episode_id"]
    )
    assert "us-west-2-warm" in allowed_hit["evidence"]


def test_retrieval_excludes_a_thread_with_any_restricted_event(monkeypatch):
    events, _, result = _compile_initial()
    monkeypatch.setitem(brain.EVENT_CLEARANCE, "r1", "sre")
    assert (
        brain.retrieve(
            result.artifacts,
            query="enterprise refund window",
            current_events=events,
            teams=frozenset(),
        )
        == []
    )
    sre_hits = brain.retrieve(
        result.artifacts,
        query="enterprise refund window",
        current_events=events,
        teams={"sre"},
    )
    assert [hit["title"] for hit in sre_hits] == ["Enterprise refund window"]


def test_topic_history_keeps_both_checkout_episodes_chronologically():
    _, _, result = _compile_initial()
    history = topic_history(
        result.artifacts, scope=brain.TENANT, topic="checkout reliability"
    )
    assert [artifact.title for artifact in history] == [
        "Checkout retry-storm failure",
        "Checkout failover region",
    ]
    assert (
        topic_history(result.artifacts, scope="other", topic="checkout reliability")
        == ()
    )


def test_compile_records_failures_when_fail_fast_is_disabled():
    episodes = segment_conversations(brain.initial_events())[:1]
    result = compile_episodes(
        episodes,
        generate=brain.reject_broken,
        cache={},
        now=brain.NOW,
        retries=1,
        fail_fast=False,
    )
    assert result.artifacts == ()
    assert result.calls == 2
    assert len(result.failed) == 1
    assert result.failed[0].attempts == 2
    assert result.failed[0].reason == "invalid episode knowledge or source evidence"


def test_compile_fail_fast_still_raises_malformed_output():
    episodes = segment_conversations(brain.initial_events())[:1]
    with pytest.raises(MalformedModelOutput):
        compile_episodes(
            episodes,
            generate=brain.reject_broken,
            cache={},
            now=brain.NOW,
            retries=1,
        )


def test_tampered_quote_is_rejected_by_strict_parser():
    events = brain.initial_events()
    episode = segment_conversations(events)[0]
    resolved = resolve_evidence(
        episode, brain.fixture(extraction_request(episode))
    ).output
    parse_episode_knowledge(episode, resolved)
    tampered = copy.deepcopy(resolved)
    tampered["claims"][0]["evidence"][0]["quote"] = "an invented quotation"
    with pytest.raises(MalformedModelOutput):
        parse_episode_knowledge(episode, tampered)


def test_resolve_evidence_is_non_mutating_and_reports_fabrication():
    events = brain.initial_events()
    episode = segment_conversations(events)[0]
    raw = brain.fixture(extraction_request(episode))
    before = copy.deepcopy(raw)
    resolved = resolve_evidence(episode, raw)
    assert raw == before
    assert [drop.reason for drop in resolved.dropped] == ["quote-not-found"]
    assert len(resolved.output["claims"]) == 2


def test_resolve_locates_short_ellipsis_fragments_regression():
    """Keep exact short fragments when resolving an ellipsis-separated quote.

    The documented resolver "splits quotes on `...`" and locates each part.
    ``refunds [...] legal`` joins two exact substrings of the refund event, but
    both are shorter than the internal ``_MINIMUM_PART`` threshold. The
    implementation then falls back to the *unsplit* quote, which still contains
    the ellipsis marker and can never match, so the whole claim is dropped
    instead of the two real spans being located.
    """
    episode = segment_conversations([brain.initial_events()[0]])[0]
    raw = {
        "title": "Refund review",
        "claims": [
            {
                "text": "Refunds need a legal review.",
                "kind": "summary",
                "status": "explicit",
                "evidence": [{"quote": "refunds [...] legal"}],
            }
        ],
    }
    resolved = resolve_evidence(episode, raw)
    assert resolved.dropped == (), [
        (drop.reason, drop.text) for drop in resolved.dropped
    ]
    quotes = [span["quote"] for span in resolved.output["claims"][0]["evidence"]]
    assert quotes == ["refunds", "legal"]


def test_segment_rejects_duplicate_event_identity():
    duplicated = [*brain.initial_events(), brain.initial_events()[0]]
    with pytest.raises(ValueError):
        segment_conversations(duplicated)


def _full_span_fixture(request):
    return {
        "title": "chunk knowledge",
        "topics": ["chunked"],
        "claims": [
            {
                "text": f"Summary of {event['event_id']}",
                "kind": "summary",
                "status": "explicit",
                "evidence": [
                    {
                        "event_id": event["event_id"],
                        "revision": event["revision"],
                        "start": 0,
                        "end": len(event["text"]),
                        "quote": event["text"],
                    }
                ],
            }
            for event in request["events"]
        ],
    }


def test_split_and_merge_rebind_chunk_knowledge_to_parent_episode():
    events = brain.initial_events()[:2]
    episode = segment_conversations(events)[0]
    chunks = split_for_output(episode, maximum_characters=40)
    assert [e.event_id for chunk in chunks for e in chunk.events] == ["r1", "r2"]
    knowledge = [
        parse_episode_knowledge(chunk, _full_span_fixture(extraction_request(chunk)))
        for chunk in chunks
    ]
    merged = merge_chunk_knowledge(knowledge, episode=episode, recipe="chunk-recipe")
    assert merged.episode == episode
    assert {span.event_id for claim in merged.claims for span in claim.evidence} == {
        "r1",
        "r2",
    }
    evidence_context(merged, current_events=events, allowed=lambda _: True)
