"""Run without credentials: python examples/conversation_knowledge_demo.py."""

from mari_components.conversation_knowledge import (
    KnowledgeEvent,
    compile_episodes,
    evidence_context,
    segment_conversations,
)


def main():
    events = (
        KnowledgeEvent(
            event_id="1",
            scope="acme",
            stream="mari",
            thread_id="t1",
            revision="r1",
            timestamp=1,
            author="Eric",
            text="Let's wait until the thread settles before extracting.",
        ),
        KnowledgeEvent(
            event_id="2",
            scope="acme",
            stream="mari",
            thread_id="t1",
            revision="r1",
            timestamp=2,
            author="Daniel",
            text="Agreed; otherwise each reply triggers another expensive call.",
        ),
    )

    def generate(request):
        # Replace with one JSON-producing model call using request instructions/events.
        return {
            "title": "Batch conversation knowledge extraction",
            "topics": ["ingestion cost"],
            "questions": ["Why does Mari delay summarizing Slack threads?"],
            "claims": [
                {
                    "text": "Eric and Daniel agreed to wait for settled threads to limit repeated calls.",
                    "kind": "decision",
                    "status": "explicit",
                    "evidence": [
                        dict(
                            event_id=e["event_id"],
                            revision=e["revision"],
                            start=0,
                            end=len(e["text"]),
                            quote=e["text"],
                        )
                        for e in request["events"]
                    ],
                }
            ],
        }

    result = compile_episodes(
        segment_conversations(events),
        generate=generate,
        cache={},
        now=1000,
        maximum_calls=1,
    )
    for artifact in result.artifacts:
        for unit in artifact.retrieval_units():
            print(f"INDEX {unit.ref.unit_id}: {unit.text}")
        print(evidence_context(artifact, current_events=events, allowed=lambda _: True))
    print(f"Extraction calls: {result.calls}")


if __name__ == "__main__":
    main()
