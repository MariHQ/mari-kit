"""Conversation-derived company brain built only from public Mari Kit APIs.

Run without credentials::

    python -m examples.company_brains.conversation

The module normalizes a small multi-thread company conversation into
``KnowledgeEvent`` values, segments it into episodes, extracts evidence-linked
knowledge with a deterministic fixture model, reuses cached artifacts, reacts to
an edit, resolves retrieved facets back to original evidence, and enforces a
host authorization predicate. No network, credentials, or provider SDKs are
used.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import replace

from mari_kit.conversation_knowledge import (
    EpisodeKnowledge,
    KnowledgeEvent,
    compile_episodes,
    evidence_context,
    segment_conversations,
)
from mari_kit.errors import MalformedModelOutput
from mari_kit.retrieval import RevisionBM25Index

TENANT = "acme"
SPACE = "knowledge"
STREAM = "slack:eng-help"
NOW = 10_000.0

# Host-owned event clearance. Events without an entry are readable by everyone;
# "p1" lives on a restricted thread and requires the "sre" team entitlement.
EVENT_CLEARANCE: dict[str, str] = {"p1": "sre"}


def _event(
    event_id: str,
    thread_id: str,
    author: str,
    timestamp: float,
    text: str,
    *,
    revision: str = "v1",
) -> KnowledgeEvent:
    return KnowledgeEvent(
        event_id=event_id,
        scope=TENANT,
        stream=STREAM,
        thread_id=thread_id,
        topic="",
        revision=revision,
        timestamp=timestamp,
        author=author,
        role="message",
        url=f"https://chat.acme.test/{thread_id}/{event_id}",
        text=text,
    )


def initial_events() -> tuple[KnowledgeEvent, ...]:
    """The source conversation, already revision-resolved by the host."""
    return (
        _event(
            "r1",
            "refund",
            "Dana",
            1.0,
            "Enterprise refunds should stay at 30 days; legal reviewed the contract language.",
        ),
        _event(
            "r2",
            "refund",
            "Lee",
            2.0,
            "Agreed, and finance already reports against the 30-day window.",
        ),
        _event(
            "i1",
            "incident",
            "Sam",
            3.0,
            "Checkout outage happened because the retry storm amplified load on the primary database.",
        ),
        _event(
            "i2",
            "incident",
            "Ravi",
            4.0,
            "Lesson: add jitter and a circuit breaker before the next launch.",
        ),
        _event(
            "o1",
            "openload",
            "Nina",
            5.0,
            "Should we migrate the ingestion pipeline to the batch scheduler this quarter?",
        ),
        _event(
            "o2",
            "openload",
            "Omar",
            6.0,
            "We should measure extraction cost per settled episode first.",
        ),
        _event(
            "p1",
            "private",
            "Eve",
            7.0,
            "The internal failover region for checkout is us-west-2-warm.",
        ),
    )


def edited_events() -> tuple[KnowledgeEvent, ...]:
    """The conversation after the host resolved an edit to the refund decision."""
    return tuple(
        replace(
            event,
            revision="v2",
            text=event.text + " This reflects the current approved wording.",
        )
        if event.event_id == "r1"
        else event
        for event in initial_events()
    )


def _claim(
    text: str,
    kind: str,
    status: str,
    quote: str,
    *,
    event_id: str = "",
) -> dict:
    """Loose model row: quote only, no offsets, sometimes a guessed event ID."""
    evidence: dict = {"quote": quote}
    if event_id:
        evidence["event_id"] = event_id
    return {"text": text, "kind": kind, "status": status, "evidence": [evidence]}


def fixture(request: dict) -> dict:
    """Deterministic stand-in for a JSON-producing model call.

    Output intentionally omits offsets and includes one unsupported claim so the
    host's ``resolve_evidence`` pass has real work to do.
    """
    identifiers = frozenset(event["event_id"] for event in request["events"])
    if identifiers == {"r1", "r2"}:
        return {
            "title": "Enterprise refund window",
            "topics": ["refund policy"],
            "questions": ["What is the enterprise refund window?"],
            "claims": [
                _claim(
                    "Enterprise refunds stay at a 30-day window.",
                    "decision",
                    "explicit",
                    "Enterprise refunds should stay at 30 days",
                    event_id="r1",
                ),
                _claim(
                    "Finance already reports against the same 30-day window.",
                    "rationale",
                    "explicit",
                    "finance already reports against the 30-day window",
                ),
                _claim(
                    "Refunds are settled in five business days.",
                    "summary",
                    "explicit",
                    "Refunds are settled in five business days",
                ),
            ],
        }
    if identifiers == {"i1", "i2"}:
        return {
            "title": "Checkout retry-storm failure",
            "topics": ["checkout reliability"],
            "questions": ["Why did checkout fail during the retry storm?"],
            "claims": [
                _claim(
                    "A retry storm amplified database load and caused the checkout outage.",
                    "failure",
                    "explicit",
                    "retry storm amplified load on the primary database",
                ),
                _claim(
                    "Add jitter and a circuit breaker before the next launch.",
                    "lesson",
                    "inferred",
                    "add jitter and a circuit breaker before the next launch",
                ),
            ],
        }
    if identifiers == {"o1", "o2"}:
        return {
            "title": "Batch scheduler migration",
            "topics": ["ingestion cost"],
            "questions": ["Should the ingestion pipeline move to the batch scheduler?"],
            "claims": [
                _claim(
                    "The team is considering moving ingestion to the batch scheduler.",
                    "open_question",
                    "unresolved",
                    "migrate the ingestion pipeline to the batch scheduler",
                ),
                _claim(
                    "Measure extraction cost per settled episode before migrating.",
                    "alternative",
                    "proposed",
                    "measure extraction cost per settled episode first",
                ),
            ],
        }
    if identifiers == {"p1"}:
        return {
            "title": "Checkout failover region",
            "topics": ["checkout reliability"],
            "questions": ["Where does checkout fail over?"],
            "claims": [
                _claim(
                    "The checkout failover region is us-west-2-warm.",
                    "summary",
                    "explicit",
                    "internal failover region for checkout is us-west-2-warm",
                ),
            ],
        }
    raise MalformedModelOutput(f"no fixture for events {sorted(identifiers)}")


def reject_broken(request: dict) -> object:
    """A callback that violates the extraction contract."""
    return {"title": "broken"}


def allowed_for(teams: Iterable[str]) -> Callable[[KnowledgeEvent], bool]:
    """Host authorization predicate shared by retrieval and evidence rendering."""
    granted = frozenset(teams)

    def allowed(event: KnowledgeEvent) -> bool:
        required = EVENT_CLEARANCE.get(event.event_id)
        return required is None or required in granted

    return allowed


def _claim_view(artifact: EpisodeKnowledge) -> list[dict]:
    return [
        {
            "text": claim.text,
            "kind": claim.kind,
            "status": claim.status,
            "evidence": [
                {
                    "event_id": item.event_id,
                    "revision": item.revision,
                    "start": item.start,
                    "end": item.end,
                    "quote": item.quote,
                }
                for item in claim.evidence
            ],
        }
        for claim in artifact.claims
    ]


def _artifact_view(artifact: EpisodeKnowledge) -> dict:
    return {
        "episode_id": artifact.episode.episode_id,
        "revision": artifact.episode.revision,
        "title": artifact.title,
        "topics": list(artifact.topics),
        "questions": list(artifact.questions),
        "claims": _claim_view(artifact),
        "cache_key": artifact.cache_key,
    }


def _by_episode(artifacts: Iterable[EpisodeKnowledge]) -> dict[str, EpisodeKnowledge]:
    return {artifact.episode.episode_id: artifact for artifact in artifacts}


def retrieve(
    artifacts: Sequence[EpisodeKnowledge],
    *,
    query: str,
    current_events: Sequence[KnowledgeEvent],
    teams: Iterable[str],
) -> list[dict]:
    """Retrieve episode facets, fuse by episode, then resolve original evidence.

    An episode is only a candidate when every one of its source events is
    authorized: a facet derived from a thread that mixes public and restricted
    messages must not surface for the unauthorized viewer.
    """
    allowed = allowed_for(teams)
    units = [unit for artifact in artifacts for unit in artifact.retrieval_units()]
    index = RevisionBM25Index({unit.ref.to_revision_ref(): unit.text for unit in units})
    allowed_refs = {
        unit.ref.to_revision_ref()
        for artifact in artifacts
        if all(allowed(event) for event in artifact.episode.events)
        for unit in artifact.retrieval_units()
    }
    artifacts_by_id = _by_episode(artifacts)
    hits: list[dict] = []
    seen: set[str] = set()
    for hit in index.search(query, limit=8, allowed_refs=allowed_refs):
        if hit.score <= 0:
            continue
        episode_id = hit.ref.object.object_id
        artifact = artifacts_by_id[episode_id]
        if episode_id in seen:
            continue
        seen.add(episode_id)
        context = evidence_context(
            artifact, current_events=current_events, allowed=allowed
        )
        hits.append(
            {
                "episode_id": episode_id,
                "unit_id": hit.ref.unit_id,
                "score": round(hit.score, 6),
                "title": artifact.title,
                "evidence": context,
            }
        )
    return hits


def try_context(
    artifact: EpisodeKnowledge,
    *,
    current_events: Sequence[KnowledgeEvent],
    teams: Iterable[str],
) -> tuple[bool, str]:
    try:
        evidence_context(
            artifact, current_events=current_events, allowed=allowed_for(teams)
        )
    except ValueError as error:
        return False, str(error)
    return True, ""


def run() -> dict:
    """Build the company brain and return a JSON-serializable report."""
    events = initial_events()
    episodes = segment_conversations(events)

    first = compile_episodes(
        episodes, generate=fixture, cache={}, now=NOW, resolve=True, maximum_calls=16
    )
    cache = {artifact.cache_key: artifact for artifact in first.artifacts}
    second = compile_episodes(
        episodes, generate=fixture, cache=cache, now=NOW, resolve=True
    )

    source_events = edited_events()
    edited_episodes = segment_conversations(source_events)
    edited = compile_episodes(
        edited_episodes, generate=fixture, cache=cache, now=NOW, resolve=True
    )
    cache.update({artifact.cache_key: artifact for artifact in edited.artifacts})
    first_by_id = _by_episode(first.artifacts)
    edited_by_id = _by_episode(edited.artifacts)
    current_artifacts = tuple(
        edited_by_id.get(episode.episode_id, first_by_id[episode.episode_id])
        for episode in episodes
    )
    refund = next(a for a in current_artifacts if a.title == "Enterprise refund window")
    old_refund = next(
        a for a in first.artifacts if a.title == "Enterprise refund window"
    )

    stale_ok, _ = try_context(
        old_refund, current_events=source_events, teams=frozenset()
    )
    deleted_ok, _ = try_context(
        refund,
        current_events=[e for e in source_events if e.event_id != "r2"],
        teams=frozenset(),
    )
    private = next(
        a for a in current_artifacts if a.title == "Checkout failover region"
    )
    sre_ok, _ = try_context(private, current_events=source_events, teams={"sre"})
    customer_ok, customer_error = try_context(
        private, current_events=source_events, teams=frozenset()
    )

    failure = compile_episodes(
        episodes[:1],
        generate=reject_broken,
        cache={},
        now=NOW,
        retries=1,
        fail_fast=False,
    )

    return {
        "tenant": TENANT,
        "space": SPACE,
        "stream": STREAM,
        "episodes": [_artifact_view(a) for a in current_artifacts],
        "extraction": {
            "first_calls": first.calls,
            "first_reused": first.reused,
            "episode_count": len(first.artifacts),
            "dropped": [
                {"reason": drop.reason, "text": drop.text} for drop in first.dropped
            ],
        },
        "cache": {
            "second_calls": second.calls,
            "second_reused": second.reused,
            "after_edit_calls": edited.calls,
            "after_edit_reused": edited.reused,
        },
        "edits": {
            "refund_episode_id": refund.episode.episode_id,
            "old_cache_key": old_refund.cache_key,
            "new_cache_key": refund.cache_key,
            "cache_key_changed": old_refund.cache_key != refund.cache_key,
            "stale_context_rejected": not stale_ok,
            "deleted_event_context_rejected": not deleted_ok,
        },
        "authorization": {
            "sre_can_render_restricted": sre_ok,
            "customer_blocked_from_restricted": not customer_ok,
            "customer_error": customer_error,
        },
        "retrieval": {
            "refund_query": retrieve(
                current_artifacts,
                query="enterprise refund window",
                current_events=source_events,
                teams=frozenset(),
            ),
            "failover_query_customer": retrieve(
                current_artifacts,
                query="checkout failover region",
                current_events=source_events,
                teams=frozenset(),
            ),
            "failover_query_sre": retrieve(
                current_artifacts,
                query="checkout failover region",
                current_events=source_events,
                teams={"sre"},
            ),
        },
        "failure_recovery": {
            "calls": failure.calls,
            "artifacts": len(failure.artifacts),
            "failed": [
                {
                    "episode_id": item.episode_id,
                    "reason": item.reason,
                    "attempts": item.attempts,
                }
                for item in failure.failed
            ],
        },
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
