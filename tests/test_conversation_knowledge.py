from dataclasses import replace

import pytest

from mari_components.conversation_knowledge import (
    KnowledgeEvent,
    compile_episodes,
    evidence_context,
    parse_episode_knowledge,
    segment_conversations,
    topic_history,
    trajectory_events,
)
from mari_components.errors import MalformedModelOutput
from mari_components.trajectories import TrajectoryRun, TrajectoryStep


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
