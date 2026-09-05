from dataclasses import replace

import pytest

from mari_components.conversation_knowledge import (
    KnowledgeEvent,
    parse_episode_knowledge,
    segment_conversations,
)
from mari_components.conversation_topics import (
    TopicGroup,
    compile_topic_briefs,
    event_vector_key,
    knowledge_vector_key,
    parse_topic_brief,
    semantic_conversation_episodes,
    semantic_topic_groups,
    topic_dependencies,
    topic_evidence_context,
    topic_request,
)
from mari_components.dependencies import plan_dependency_updates
from mari_components.errors import MalformedModelOutput


def event(i, **changes):
    return replace(
        KnowledgeEvent(
            event_id=str(i),
            revision="r1",
            scope="acme",
            stream="mari",
            timestamp=float(i),
            author="Eric",
            text=f"Observation {i}",
        ),
        **changes,
    )


def artifact(e):
    episode = segment_conversations([e])[0]
    return parse_episode_knowledge(
        episode,
        {
            "title": e.text,
            "topics": [],
            "questions": ["Why batch extraction?"],
            "claims": [
                {
                    "text": e.text,
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
        },
    )


def response(request):
    ids = list(request["claims"])
    return {
        "title": "Batching decisions",
        "links": [
            {
                "source": ids[1],
                "target": ids[0],
                "relation": "contradicts",
                "rationale": "The two proposals differ.",
            }
        ]
        if len(ids) > 1
        else [],
    }


def compile_groups(groups, **kwargs):
    defaults = dict(
        generate=response,
        cache={},
        current_events=[e for g in groups for a in g.members for e in a.episode.events],
        allowed=lambda _: True,
        count_tokens=lambda _: 100,
        output_token_reserve=50,
    )
    defaults.update(kwargs)
    return compile_topic_briefs(groups, **defaults)


def test_interleaved_topics_preserve_sources_threads_and_order():
    a, b, c = event(1), event(2), event(3)
    t = event(4, thread_id="explicit")
    vectors = {
        event_vector_key(a): [1, 0],
        event_vector_key(b): [0, 1],
        event_vector_key(c): [1, 0],
    }
    episodes = semantic_conversation_episodes([c, t, b, a], vectors=vectors)
    assert [e.events for e in episodes] == [(a, c), (b,), (t,)]
    assert episodes == semantic_conversation_episodes([a, b, c, t], vectors=vectors)
    assert all(e.topic == "" for ep in episodes for e in ep.events)


def test_event_grouping_boundaries_and_stale_vectors():
    a = event(1)
    b = event(2, scope="other")
    c = event(3, stream="other")
    d = event(4, timestamp=9000)
    rows = [a, b, c, d]
    vectors = {event_vector_key(e): [1, 0] for e in rows}
    assert len(semantic_conversation_episodes(rows, vectors=vectors)) == 4
    with pytest.raises(KeyError):
        semantic_conversation_episodes([replace(a, text="edited")], vectors=vectors)
    with pytest.raises(ValueError):
        semantic_conversation_episodes([a, a], vectors=vectors)
    with pytest.raises(ValueError):
        semantic_conversation_episodes(rows, vectors=vectors, maximum_events=1)


@pytest.mark.parametrize("bad", [[0, 0], [float("nan"), 1], [float("inf"), 1], []])
def test_invalid_embeddings(bad):
    a = artifact(event(1))
    with pytest.raises(ValueError):
        semantic_topic_groups([a], vectors={knowledge_vector_key(a): bad})


def test_complete_link_prevents_transitive_topic_drift():
    # A~B, B~C, but A !~ C: connected components would incorrectly merge all.
    a, b, c = [artifact(event(i)) for i in (1, 2, 3)]
    groups = semantic_topic_groups(
        [c, a, b],
        vectors={
            knowledge_vector_key(a): [1, 0],
            knowledge_vector_key(b): [0.8, 0.6],
            knowledge_vector_key(c): [0.28, 0.96],
        },
        similarity_threshold=0.75,
    )
    assert [g.members for g in groups] == [(a, b), (c,)]


def test_cross_day_stream_topics_scope_and_actual_output_revisions():
    a = artifact(event(1))
    b = artifact(event(2, timestamp=86400, stream="engineering"))
    c = artifact(event(3, scope="other"))
    groups = semantic_topic_groups(
        [a, b, c], vectors={knowledge_vector_key(x): [1, 0] for x in (a, b, c)}
    )
    assert [g.members for g in groups] == [(a, b), (c,)]
    assert knowledge_vector_key(a) != knowledge_vector_key(
        replace(a, title="new output, same recipe")
    )


@pytest.mark.parametrize(
    "change",
    [
        {"source": "missing"},
        {"target": "missing"},
        {"relation": "delete"},
        {"rationale": ""},
        {"source": []},
    ],
)
def test_bad_relationships_rejected(change):
    group = TopicGroup(members=(artifact(event(1)), artifact(event(2))))
    output = response(topic_request(group))
    output["links"][0].update(change)
    with pytest.raises(MalformedModelOutput):
        parse_topic_brief(group, output)


def test_self_links_duplicates_and_valid_empty_links():
    group = TopicGroup(members=(artifact(event(1)), artifact(event(2))))
    output = response(topic_request(group))
    output["links"][0]["source"] = output["links"][0]["target"]
    with pytest.raises(MalformedModelOutput):
        parse_topic_brief(group, output)
    output = response(topic_request(group))
    output["links"] *= 2
    with pytest.raises(MalformedModelOutput):
        parse_topic_brief(group, output)
    assert (
        parse_topic_brief(group, {"title": "No relationship", "links": []}).links == ()
    )


def test_budget_cache_incremental_receipts_and_retirement():
    a, b, c = [artifact(event(i)) for i in (1, 2, 3)]
    groups = [TopicGroup(members=(a, b)), TopicGroup(members=(c,))]
    first = compile_groups(groups, maximum_calls=1)
    assert first.calls == 1 and first.reserved_tokens == 150 and len(first.pending) == 1
    second = compile_groups(groups, cache={v.cache_key: v for v in first.briefs})
    assert second.calls == 1 and second.reused == 1
    assert len(compile_groups(groups, maximum_tokens=149).pending) == 2
    cache = {v.cache_key: v for v in second.briefs}
    assert compile_groups(groups, cache=cache, maximum_calls=0).reused == 2
    changed = [TopicGroup(members=(replace(a, title="changed"), b)), groups[1]]
    assert compile_groups(changed, cache=cache).calls == 1
    assert compile_groups(changed, cache=cache).briefs == compile_groups(changed).briefs
    assert compile_groups(groups, cache=cache, recipe="v2").calls == 2
    removed = compile_groups(
        [groups[1]], previous_topic_ids=[g.topic_id for g in groups]
    )
    assert removed.retired == (groups[0].topic_id,)
    specs_and_stamps = [topic_dependencies(g, recipe="topic-links-v1") for g in groups]
    plan = plan_dependency_updates(
        derivations=[spec for spec, _ in specs_and_stamps],
        sources=[s for _, stamps in specs_and_stamps for s in stamps],
        materializations=second.receipts,
    )
    assert all(u.action.value == "reuse" for u in plan.updates)


def test_embedding_dimensions_member_limits_and_malformed_output():
    a, b = artifact(event(1)), artifact(event(2))
    vectors = {knowledge_vector_key(a): [1, 0], knowledge_vector_key(b): [1, 0]}
    assert len(semantic_topic_groups([a, b], vectors=vectors, maximum_members=1)) == 2
    with pytest.raises(ValueError):
        semantic_topic_groups([a, b], vectors=vectors, maximum_candidates=1)
    vectors[knowledge_vector_key(b)] = [1]
    with pytest.raises(ValueError):
        semantic_topic_groups([a, b], vectors=vectors)
    with pytest.raises(MalformedModelOutput):
        compile_groups([TopicGroup(members=(a, b))], generate=lambda _: {})


def test_membership_changes_and_source_edits_rebuild_and_retire():
    a, b = artifact(event(1)), artifact(event(2))
    original = TopicGroup(members=(a, b))
    first = compile_groups([original])
    cache = {v.cache_key: v for v in first.briefs}
    changed = TopicGroup(
        members=(a, artifact(event(2, text="New position", revision="r2")))
    )
    assert changed.topic_id == original.topic_id
    assert changed.revision != original.revision
    assert compile_groups([changed], cache=cache).calls == 1
    split = [TopicGroup(members=(a,)), TopicGroup(members=(b,))]
    result = compile_groups(split, cache=cache, previous_topic_ids=[original.topic_id])
    assert result.retired == (original.topic_id,)
    assert result.briefs == compile_groups(split).briefs
    assert compile_groups([], previous_topic_ids=[original.topic_id]).retired == (
        original.topic_id,
    )


def test_sources_preflight_before_calls_and_rechecked_for_cached_rendering():
    a, b = artifact(event(1)), artifact(event(2))
    group = TopicGroup(members=(a, b))
    calls = []
    with pytest.raises(ValueError):
        compile_groups(
            [group],
            allowed=lambda e: e.event_id != "2",
            generate=lambda r: calls.append(r),
        )
    assert calls == []
    result = compile_groups([group])
    brief = result.briefs[0]
    events = [event(1), event(2)]
    text = topic_evidence_context(brief, current_events=events, allowed=lambda _: True)
    assert "proposed relationship; not verified" in text
    assert "Observation 1" in text and "Observation 2" in text
    assert {u.ref.unit_id for u in brief.retrieval_units()} == {"brief", "questions"}
    for current in [events[:1], [replace(events[0], text="edited"), events[1]]]:
        with pytest.raises(ValueError):
            topic_evidence_context(
                brief, current_events=current, allowed=lambda _: True
            )
    with pytest.raises(ValueError):
        compile_groups([group], cache={brief.cache_key: brief}, allowed=lambda _: False)
