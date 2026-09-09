import copy
from dataclasses import replace

import pytest

from mari_kit.conversation_knowledge import (
    CLAIM_KINDS,
    EpisodeFailure,
    KnowledgeEpisode,
    KnowledgeEvent,
    compile_episodes,
    evidence_context,
    extraction_request,
    merge_chunk_knowledge,
    parse_episode_knowledge,
    resolve_evidence,
    segment_conversations,
    split_for_output,
    topic_history,
    trajectory_events,
)
from mari_kit.errors import MalformedModelOutput, TransientFailure
from mari_kit.trajectories import TrajectoryRun, TrajectoryStep


def event(identifier="1", **kwargs):
    return KnowledgeEvent(
        event_id=identifier,
        scope="company",
        stream="mari",
        revision="r1",
        timestamp=float(identifier),
        author="Eric",
        text="Let's batch ingestion after discussions settle.",
        **kwargs,
    )


def output(episode):
    e = episode.events[0]
    return {
        "title": "Delayed conversation ingestion",
        "topics": ["ingestion"],
        "questions": ["Why wait before processing conversations?"],
        "claims": [
            {
                "text": "Eric proposed batching after discussion settles.",
                "kind": "decision",
                "status": "proposed",
                "evidence": [
                    {
                        "event_id": e.event_id,
                        "revision": e.revision,
                        "start": 0,
                        "end": len(e.text),
                        "quote": e.text,
                    }
                ],
            }
        ],
    }


def test_threads_scope_topic_and_hard_bounds():
    a = event(thread_id="one")
    b = replace(event("2", thread_id="one"), timestamp=9000)
    c = event("3", thread_id="two")
    episodes = segment_conversations([c, b, a])
    assert any(e.events == (a, b) for e in episodes)
    assert len(segment_conversations([a, replace(a, scope="other")])) == 2
    assert len(segment_conversations([a, b], maximum_characters=len(a.text))) == 2
    assert (
        len(segment_conversations([replace(a, thread_id=""), replace(b, thread_id="")]))
        == 2
    )
    with pytest.raises(ValueError):
        segment_conversations([a, a])


@pytest.mark.parametrize(
    "change",
    [
        {"revision": "wrong"},
        {"quote": "invented"},
        {"event_id": "absent"},
        {"start": -1},
        {"start": True},
        {"end": 99999},
    ],
)
def test_rejects_bad_evidence(change):
    episode = segment_conversations([event()])[0]
    value = output(episode)
    value["claims"][0]["evidence"][0].update(change)
    with pytest.raises(MalformedModelOutput):
        parse_episode_knowledge(episode, value)


def test_search_vocabulary_and_original_evidence():
    episode = segment_conversations([event()])[0]
    artifact = parse_episode_knowledge(episode, output(episode))
    units = artifact.retrieval_units()
    assert {u.ref.unit_id for u in units} == {"summary", "questions", "topics"}
    assert "processing conversations" not in event().text
    assert "processing conversations" in units[1].text
    text = evidence_context(
        artifact, current_events=episode.events, allowed=lambda e: True
    )
    assert "proposed" in text and event().text in text
    assert topic_history([artifact], scope="other", topic="ingestion") == ()
    assert topic_history([artifact], scope="company", topic="ingestion") == (artifact,)
    with pytest.raises(ValueError):
        evidence_context(
            artifact, current_events=episode.events, allowed=lambda e: False
        )
    with pytest.raises(ValueError):
        evidence_context(
            artifact,
            current_events=[replace(event(), text="changed")],
            allowed=lambda e: True,
        )


def test_call_budget_settling_and_revision_cache():
    episodes = segment_conversations([event(thread_id="a"), event("2", thread_id="b")])

    def generate(request):
        episode = next(
            e
            for e in episodes
            if e.events[0].event_id == request["events"][0]["event_id"]
        )
        return output(episode)

    pending = compile_episodes(episodes, generate=generate, cache={}, now=2)
    assert pending.calls == 0 and len(pending.pending) == 2
    first = compile_episodes(
        episodes, generate=generate, cache={}, now=1000, maximum_calls=1
    )
    assert first.calls == 1 and len(first.pending) == 1
    cache = {a.cache_key: a for a in first.artifacts}
    second = compile_episodes(episodes, generate=generate, cache=cache, now=1000)
    assert second.calls == second.reused == 1
    changed = segment_conversations([replace(event(thread_id="a"), revision="r2")])[0]
    assert changed.episode_id == episodes[0].episode_id
    assert changed.revision != episodes[0].revision
    assert (
        compile_episodes(
            [changed], generate=lambda _: output(changed), cache=cache, now=1000
        ).calls
        == 1
    )


def test_trajectory_requires_observations_and_preserves_failure():
    run = TrajectoryRun(
        trajectory_id="run",
        outcome="failure",
        steps=(
            TrajectoryStep(0, "test", "execute", ok=False),
            TrajectoryStep(1, "read", "inspect", ok=True),
        ),
    )
    assert trajectory_events(run, scope="company", revision="r1", observations={}) == ()
    events = trajectory_events(
        run,
        scope="company",
        revision="r1",
        observations={0: "Duplicate output after replay."},
    )
    assert "Run outcome: failure" in events[0].text
    assert "Duplicate output" in events[0].text
    with pytest.raises(ValueError):
        trajectory_events(
            run, scope="company", revision="r1", observations={9: "unknown"}
        )


def loose_claim(quote, *, event_id="1", **overrides):
    row = {
        "text": "Eric wants ingestion batched.",
        "kind": "decision",
        "status": "proposed",
        "evidence": [{"event_id": event_id, "quote": quote}],
    }
    row.update(overrides)
    return row


def two_event_episode():
    second = replace(
        event("2"), text="Fine by me.\nEach reply costs another call anyway."
    )
    return KnowledgeEpisode(episode_id="ep", revision="rev", events=(event(), second))


def test_resolve_recomputes_spans_and_passes_strict_parser():
    episode = two_event_episode()
    raw = {"title": "Batching", "claims": [loose_claim("batch ingestion")]}
    before = copy.deepcopy(raw)
    resolved = resolve_evidence(episode, raw)
    assert raw == before and resolved.dropped == ()
    span = resolved.output["claims"][0]["evidence"][0]
    assert span == {
        "event_id": "1",
        "revision": "r1",
        "start": 6,
        "end": 21,
        "quote": "batch ingestion",
    }
    artifact = parse_episode_knowledge(episode, resolved.output)
    assert artifact.claims[0].evidence[0].quote == "batch ingestion"
    assert resolve_evidence(episode, "not a dict").output == {}
    with pytest.raises(MalformedModelOutput):
        parse_episode_knowledge(episode, resolve_evidence(episode, []).output)


def test_resolve_keeps_valid_spans_and_tolerates_whitespace_drift():
    episode = two_event_episode()
    exact = output(episode)["claims"][0]
    drifted = loose_claim("Fine by me. Each  reply costs", event_id="2")
    resolved = resolve_evidence(episode, {"claims": [exact, drifted]})
    assert resolved.output["claims"][0]["evidence"] == exact["evidence"]
    span = resolved.output["claims"][1]["evidence"][0]
    assert span["quote"] == "Fine by me.\nEach reply costs"
    assert episode.events[1].text[span["start"] : span["end"]] == span["quote"]


def test_resolve_splits_ellipsis_quotes():
    episode = two_event_episode()
    claim = loose_claim("Let's batch ingestion ... discussions settle.")
    spans = resolve_evidence(episode, {"claims": [claim]}).output["claims"][0][
        "evidence"
    ]
    assert [s["quote"] for s in spans] == [
        "Let's batch ingestion",
        "discussions settle.",
    ]
    assert spans[0]["end"] <= spans[1]["start"]
    unicode = loose_claim("Let's batch ingestion […] tiny")
    only = resolve_evidence(episode, {"claims": [unicode]}).output["claims"][0]
    assert [s["quote"] for s in only["evidence"]] == ["Let's batch ingestion"]


def test_resolve_falls_back_to_the_right_event():
    episode = two_event_episode()
    wrong = loose_claim("costs another call", event_id=" <1> ")
    missing = loose_claim("costs another call", event_id="nope")
    claims = resolve_evidence(episode, {"claims": [wrong, missing]}).output["claims"]
    assert all(c["evidence"][0]["event_id"] == "2" for c in claims)
    assert all(c["evidence"][0]["revision"] == "r1" for c in claims)


def test_resolve_drops_unresolvable_claims_with_reasons():
    episode = two_event_episode()
    rows = [
        loose_claim("this never appears anywhere"),
        loose_claim("x", evidence=[]),
        loose_claim("x", evidence=None),
        loose_claim("x", text="   "),
        "not a row",
        loose_claim("batch ingestion"),
    ]
    resolved = resolve_evidence(episode, {"claims": rows}, maximum_claims=1)
    assert [d.reason for d in resolved.dropped] == [
        "quote-not-found",
        "no-evidence",
        "no-evidence",
        "empty-text",
        "bad-row",
    ]
    assert all(d.episode_id == "ep" for d in resolved.dropped)
    assert len(resolved.output["claims"]) == 1
    extra = resolve_evidence(episode, {"claims": rows[-1:] * 3}, maximum_claims=2)
    assert [d.reason for d in extra.dropped] == ["claim-cap"]
    with pytest.raises(ValueError):
        resolve_evidence(episode, {}, maximum_claims=0)


def test_resolve_maps_aliases_and_unknown_kinds():
    episode = two_event_episode()
    rows = [
        loose_claim("batch ingestion", kind="Warning", status="stated"),
        loose_claim("batch ingestion", kind="question", status="open"),
        loose_claim("batch ingestion", kind="mystery", status=7),
    ]
    claims = resolve_evidence(episode, {"claims": rows}).output["claims"]
    assert [(c["kind"], c["status"]) for c in claims] == [
        ("failure", "explicit"),
        ("open_question", "unresolved"),
        ("summary", "explicit"),
    ]
    parse_episode_knowledge(episode, {"title": "t", "claims": claims})


def test_resolve_defaults_title_and_sanitizes_hints():
    episode = two_event_episode()
    raw = {
        "title": "  ",
        "topics": ["a", " ", 3, "a", "b"] + [str(i) for i in range(20)],
        "questions": "Why wait?",
        "claims": [loose_claim("batch ingestion")],
    }
    out = resolve_evidence(episode, raw).output
    assert out["title"] == "Let's batch ingestion after discussions settle."
    assert out["topics"][:3] == ["a", "b", "0"] and len(out["topics"]) == 12
    assert out["questions"] == ["Why wait?"]
    assert resolve_evidence(episode, {"topics": None}).output["topics"] == []
    parse_episode_knowledge(episode, out)


def test_compile_with_resolve_collects_dropped():
    episode = segment_conversations([event()])[0]
    raw = {"claims": [loose_claim("batch ingestion"), loose_claim("nope nope nope")]}
    result = compile_episodes(
        [episode], generate=lambda _: raw, cache={}, now=1000, resolve=True
    )
    assert len(result.artifacts) == 1 and result.failed == ()
    assert [d.reason for d in result.dropped] == ["quote-not-found"]
    assert result.dropped[0].episode_id == episode.episode_id
    with pytest.raises(MalformedModelOutput):
        compile_episodes([episode], generate=lambda _: raw, cache={}, now=1000)


def test_compile_retry_sends_prior_error_and_succeeds():
    episode = segment_conversations([event()])[0]
    seen = []

    def generate(request):
        seen.append(request.get("prior_error"))
        if len(seen) == 1:
            return {"title": "broken"}
        return output(episode)

    result = compile_episodes(
        [episode], generate=generate, cache={}, now=1000, retries=1
    )
    assert result.calls == 2 and len(result.artifacts) == 1
    assert seen[0] is None and "invalid episode knowledge" in seen[1]


def test_compile_retry_budget_counts_against_maximum_calls():
    episodes = segment_conversations([event(thread_id="a"), event("2", thread_id="b")])
    result = compile_episodes(
        episodes,
        generate=lambda _: None,
        cache={},
        now=1000,
        retries=5,
        maximum_calls=1,
        fail_fast=False,
    )
    assert result.calls == 1 and result.artifacts == ()
    assert result.failed == (
        EpisodeFailure(
            episode_id=episodes[0].episode_id,
            reason="invalid episode knowledge or source evidence",
            attempts=1,
        ),
    )
    assert result.pending == (episodes[1].episode_id,)


def test_compile_fail_fast_false_records_failure_and_continues():
    episodes = segment_conversations([event(thread_id="a"), event("2", thread_id="b")])

    def generate(request):
        if request["events"][0]["event_id"] == "1":
            raise TransientFailure("provider busy")
        return output(episodes[1])

    result = compile_episodes(
        episodes, generate=generate, cache={}, now=1000, retries=2, fail_fast=False
    )
    assert result.calls == 4 and len(result.artifacts) == 1
    assert result.failed[0].attempts == 3 and result.failed[0].reason == "provider busy"
    assert result.artifacts[0].episode == episodes[1]


def test_compile_fail_fast_true_still_raises():
    episode = segment_conversations([event()])[0]

    def generate(_):
        raise ValueError("bad generator")

    with pytest.raises(ValueError):
        compile_episodes([episode], generate=generate, cache={}, now=1000, retries=1)
    with pytest.raises(MalformedModelOutput):
        compile_episodes(
            [episode], generate=lambda _: {}, cache={}, now=1000, retries=1
        )
    with pytest.raises(ValueError):
        compile_episodes([episode], generate=generate, cache={}, now=1000, retries=-1)


def test_split_for_output_windows_and_overlap():
    events = tuple(replace(event(str(i)), text="x" * 10) for i in range(1, 5))
    episode = KnowledgeEpisode(episode_id="ep", revision="rev", events=events)
    chunks = split_for_output(episode, maximum_characters=25)
    assert [c.episode_id for c in chunks] == ["ep#0", "ep#1", "ep#2"]
    assert [[e.event_id for e in c.events] for c in chunks] == [
        ["1", "2"],
        ["2", "3"],
        ["3", "4"],
    ]
    assert len({c.revision for c in chunks}) == 3
    plain = split_for_output(episode, maximum_characters=25, overlap_events=0)
    assert [[e.event_id for e in c.events] for c in plain] == [["1", "2"], ["3", "4"]]
    assert split_for_output(episode, maximum_characters=40) == (episode,)
    with pytest.raises(ValueError):
        split_for_output(episode, maximum_characters=0)


def test_split_for_output_oversized_event_gets_own_window():
    small = replace(event("1"), text="x" * 5)
    huge = replace(event("2"), text="y" * 50)
    tail = replace(event("3"), text="z" * 5)
    episode = KnowledgeEpisode(
        episode_id="ep", revision="rev", events=(small, huge, tail)
    )
    chunks = split_for_output(episode, maximum_characters=20)
    assert [[e.event_id for e in c.events] for c in chunks] == [["1"], ["2"], ["3"]]
    assert chunks[1].events[0].text == huge.text
    alone = KnowledgeEpisode(episode_id="ep", revision="rev", events=(huge,))
    assert split_for_output(alone, maximum_characters=20) == (alone,)


def test_merge_chunk_knowledge_dedups_and_validates():
    events = (
        event(),
        replace(event("2"), text="Fine by me."),
        replace(event("3"), text="Each reply costs another call anyway."),
    )
    episode = KnowledgeEpisode(episode_id="ep", revision="rev", events=events)
    first, second = split_for_output(episode, maximum_characters=60)
    assert [e.event_id for e in first.events] == ["1", "2"]
    assert [e.event_id for e in second.events] == ["2", "3"]
    shared = loose_claim("Fine by me.", kind="summary", status="explicit")
    a = parse_episode_knowledge(
        first,
        resolve_evidence(
            first, {"title": "A", "topics": ["t1"], "claims": [shared]}
        ).output,
    )
    b = parse_episode_knowledge(
        second,
        resolve_evidence(
            second,
            {
                "title": "B",
                "topics": ["t2", "t1"],
                "questions": ["Why?"],
                "claims": [shared, loose_claim("costs another call", event_id="3")],
            },
        ).output,
    )
    assert a.claims[0] == b.claims[0]
    merged = merge_chunk_knowledge([a, b], episode=episode, recipe="r")
    assert merged.episode is episode and merged.title == "A" and merged.recipe == "r"
    assert len(merged.claims) == 2 and merged.topics == ("t1", "t2")
    assert merged.questions == ("Why?",)
    assert {s.event_id for c in merged.claims for s in c.evidence} == {"2", "3"}
    evidence_context(merged, current_events=episode.events, allowed=lambda e: True)
    other = KnowledgeEpisode(
        episode_id="x", revision="rev", events=(replace(event("9"), text="unrelated"),)
    )
    with pytest.raises(ValueError):
        merge_chunk_knowledge([a, b], episode=other, recipe="r")
    with pytest.raises(ValueError):
        merge_chunk_knowledge([], episode=episode, recipe="r")


def test_extraction_request_lens_and_kinds():
    episode = segment_conversations([event()])[0]
    default = extraction_request(episode)
    assert "kinds" not in default
    lensed = extraction_request(episode, lens="  Focus on cost.  ")
    assert lensed["instructions"] == default["instructions"] + " Focus on cost."
    assert lensed["events"] == default["events"]
    narrow = extraction_request(episode, kinds={"failure", "decision"})
    assert narrow["kinds"] == ["decision", "failure"]
    assert "kind (decision, failure)" in narrow["instructions"]
    assert "lesson, procedure" not in narrow["instructions"]
    assert extraction_request(episode, kinds=CLAIM_KINDS)["kinds"] == sorted(
        CLAIM_KINDS
    )
    for bad in ({}, {"decision", "rumor"}, "decision"):
        with pytest.raises(ValueError):
            extraction_request(episode, kinds=bad)


def test_merge_rejects_chunks_with_stale_uncited_events():
    old_b = replace(event("2"), text="Staging only.")
    chunk = KnowledgeEpisode(episode_id="ep#0", revision="c", events=(event(), old_b))
    knowledge = parse_episode_knowledge(
        chunk,
        resolve_evidence(chunk, {"claims": [loose_claim("batch ingestion")]}).output,
    )
    new_b = replace(event("2"), text="Production only.", revision="r2")
    parent = KnowledgeEpisode(episode_id="ep", revision="p", events=(event(), new_b))
    with pytest.raises(ValueError):
        merge_chunk_knowledge([knowledge], episode=parent, recipe="r")
    same = KnowledgeEpisode(episode_id="ep", revision="p", events=(event(), old_b))
    merged = merge_chunk_knowledge([knowledge], episode=same, recipe="r")
    evidence_context(merged, current_events=same.events, allowed=lambda e: True)


def test_resolve_prefers_exact_event_ids_over_normalized_forms():
    text = "Ship it after the freeze."
    upper = replace(event("1"), event_id="A", author="Ann", text=text)
    lower = replace(event("2"), event_id="a", author="Bob", text=text)
    episode = KnowledgeEpisode(episode_id="ep", revision="rev", events=(upper, lower))
    claims = resolve_evidence(
        episode,
        {
            "claims": [
                loose_claim("after the freeze", event_id="a"),
                loose_claim("after the freeze", event_id="A"),
                loose_claim("after the freeze", event_id=" <a> "),
            ]
        },
    ).output["claims"]
    hits = [c["evidence"][0]["event_id"] for c in claims]
    assert hits == ["a", "A", "A"]
    authors = {e.event_id: e.author for e in episode.events}
    assert [authors[h] for h in hits] == ["Bob", "Ann", "Ann"]
