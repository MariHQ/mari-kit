"""Credential-free semantic grouping and incremental consolidation fixture.

Run: PYTHONPATH=src python examples/conversation_topics_demo.py
Vectors and extraction/model outputs are planted, NOT a semantic benchmark.
"""

import json

from mari_components.conversation_knowledge import (
    KnowledgeEvent,
    compile_episodes,
)
from mari_components.conversation_topics import (
    compile_topic_briefs,
    event_vector_key,
    knowledge_vector_key,
    semantic_conversation_episodes,
    semantic_topic_groups,
    topic_evidence_context,
)


def run():
    rows = [
        ("1", 1, "Eric", "Wait until it settles before extracting.", [1, 0]),
        ("2", 2, "Daniel", "The deploy is blocked on CI.", [0, 1]),
        ("3", 3, "Daniel", "Agreed: each reply otherwise costs another call.", [1, 0]),
        (
            "4",
            86400,
            "Eric",
            "For urgent threads, I propose immediate extraction.",
            [1, 0],
        ),
    ]
    events = tuple(
        KnowledgeEvent(
            event_id=i,
            timestamp=t,
            author=author,
            text=text,
            revision="r1",
            scope="company",
            stream="mari",
        )
        for i, t, author, text, _ in rows
    )
    vectors = {
        event_vector_key(e): row[-1] for e, row in zip(events, rows, strict=True)
    }
    episodes = semantic_conversation_episodes(events, vectors=vectors)

    def extract(request):
        sources = request["events"]
        return {
            "title": "Deployment"
            if sources[0]["event_id"] == "2"
            else "Extraction timing",
            "topics": [],
            "questions": ["When should conversation extraction run?"],
            "claims": [
                {
                    "text": e["text"],
                    "kind": "summary",
                    "status": "explicit",
                    "evidence": [
                        {
                            "event_id": e["event_id"],
                            "revision": e["revision"],
                            "start": 0,
                            "end": len(e["text"]),
                            "quote": e["text"],
                        }
                    ],
                }
                for e in sources
            ],
        }

    extracted = compile_episodes(episodes, generate=extract, cache={}, now=90000)
    topic_vectors = {
        knowledge_vector_key(a): [0, 1] if a.title == "Deployment" else [1, 0]
        for a in extracted.artifacts
    }
    groups = semantic_topic_groups(extracted.artifacts, vectors=topic_vectors)

    def relate(request):
        ids = list(request["claims"])
        return {
            "title": "Conversation extraction timing"
            if len(ids) > 1
            else "Deployment status",
            "links": [
                {
                    "source": ids[-1],
                    "target": ids[0],
                    "relation": "extends",
                    "rationale": "An urgent-thread exception is proposed; it is not an approved replacement.",
                }
            ]
            if len(ids) > 1
            else [],
        }

    options = dict(
        generate=relate,
        current_events=events,
        allowed=lambda _: True,
        # Fixture-only conservative reservation; use the provider tokenizer in production.
        count_tokens=lambda r: len(json.dumps(r).encode("utf-8")),
        maximum_tokens=20000,
    )
    first = compile_topic_briefs(groups, cache={}, **options)
    second = compile_topic_briefs(
        groups, cache={b.cache_key: b for b in first.briefs}, **options
    )
    assert second.calls == 0
    assert second.briefs == first.briefs
    for brief in first.briefs:
        print(
            topic_evidence_context(brief, current_events=events, allowed=lambda _: True)
        )
    result = {
        "events": len(events),
        "episodes": len(episodes),
        "topics": len(groups),
        "extraction_calls": extracted.calls,
        "consolidation_calls": first.calls,
        "unchanged_consolidation_calls": second.calls,
    }
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    run()
