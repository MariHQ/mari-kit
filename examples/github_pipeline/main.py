"""Poll GitHub → process webhook hint → poll again to repair a missed event."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Iterable, Mapping

import numpy as np

from mari_components.connectors import GitHubConfig, poll_github, validate_github
from mari_components.connectors.events import (
    coalesce_hints, github_change_hint, parse_json_object, verify_hmac_sha256,
)
from mari_components.knowledge import answer_question
from mari_components.retrieval import build_index, search_index
from mari_components.sync import SyncState, plan_sync
from mari_components.types import KnowledgeDocument, PollPage, PollRequest, SyncMode

from examples.support import (
    FakeGitHub, embed_document, json_generator, required, selected_mode, token_vectors,
    urllib_transport,
)


def _apply(
    documents: dict[str, KnowledgeDocument],
    vectors: dict[str, np.ndarray],
    embedded: list[str],
    state: SyncState,
    pages: Iterable[PollPage],
    *,
    mode: SyncMode,
) -> tuple[SyncState, tuple[str, ...], tuple[str, ...]]:
    changed: list[str] = []
    deleted: list[str] = []
    for page in pages:
        plan = plan_sync(state, page, mode=mode)
        for document in plan.upserts:
            previous = documents.get(document.external_id)
            documents[document.external_id] = document
            if previous is None or previous.title != document.title or previous.body != document.body:
                vectors[document.external_id] = embed_document(document)
                embedded.append(document.external_id)
            changed.append(document.external_id)
        for tombstone in plan.deletes:
            documents.pop(tombstone.external_id, None)
            vectors.pop(tombstone.external_id, None)
            deleted.append(tombstone.external_id)
        state = plan.state
    return state, tuple(changed), tuple(deleted)


def _fake_event(secret: str) -> tuple[bytes, str, str]:
    raw = json.dumps({
        "repository": {"full_name": "acme/knowledge"},
        "ref": "refs/heads/main",
        "commits": [{
            "added": [], "modified": ["README.md"], "removed": ["docs/release.md"],
        }],
    }, separators=(",", ":")).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return raw, signature, "push"


def run(environment: Mapping[str, str] | None = None) -> dict[str, object]:
    env = os.environ if environment is None else environment
    mode = selected_mode(env)
    token = required(env, "GITHUB_TOKEN")
    repository = required(env, "GITHUB_REPOSITORY")
    paths = required(env, "GITHUB_PATHS")
    webhook_secret = required(env, "GITHUB_WEBHOOK_SECRET")
    provider = FakeGitHub() if mode == "fake" else urllib_transport
    config = GitHubConfig(
        token, repository,
        paths=tuple(value.strip() for value in paths.split(",") if value.strip()),
    )
    validation = validate_github(config, http=provider)
    if not validation.ok:
        raise RuntimeError(validation.message)

    documents: dict[str, KnowledgeDocument] = {}
    vectors: dict[str, np.ndarray] = {}
    embedded: list[str] = []
    state, initial_upserts, _ = _apply(
        documents, vectors, embedded, SyncState(),
        poll_github(config, PollRequest(mode=SyncMode.FULL), http=provider),
        mode=SyncMode.FULL,
    )
    initial_cursor_advanced = bool(state.cursor)
    initial_index = build_index(vectors)
    hits = search_index(
        initial_index, token_vectors("How do I deploy a release?"),
        limit=min(2, len(vectors)),
    )

    answer = ""
    citations: tuple[str, ...] = ()
    if "file:docs/release.md" in documents:
        generator = json_generator(env, lambda _prompt, _version: {
            "answer": "Release Mari by deploying the tested main branch.",
            "evidence": [{
                "document_id": "file:docs/release.md",
                "quote": "Release Mari by deploying the tested main branch.",
            }],
        })
        grounded = answer_question(
            "How do I release the product?", (documents["file:docs/release.md"],),
            generate_json=generator,
        )
        answer = grounded.answer
        citations = tuple(item.document_id for item in grounded.evidence)

    if mode == "fake":
        provider.update()
        raw, signature, event_name = _fake_event(webhook_secret)
    else:
        raw = required(env, "GITHUB_WEBHOOK_JSON").encode()
        signature = required(env, "GITHUB_WEBHOOK_SIGNATURE")
        event_name = required(env, "GITHUB_WEBHOOK_EVENT")
    verify_hmac_sha256(raw, signature, webhook_secret)
    hint = github_change_hint(event_name, parse_json_object(raw))
    hints = coalesce_hints((hint, hint))
    # A webhook is only a dirty hint. Canonical state still comes from the
    # connector poll, sharing the same cursor and manifest as scheduled work.
    state, event_changed, event_deleted = _apply(
        documents, vectors, embedded, state,
        poll_github(
            config, PollRequest(SyncMode.INCREMENTAL, state.cursor, state.checkpoint),
            http=provider,
        ),
        mode=SyncMode.INCREMENTAL,
    )

    # Simulate a lost webhook. Scheduled polling must independently discover
    # and apply the repository's next canonical head.
    if mode == "fake":
        provider.publish_without_event()
    state, polling_changed, polling_deleted = _apply(
        documents, vectors, embedded, state,
        poll_github(
            config, PollRequest(SyncMode.INCREMENTAL, state.cursor, state.checkpoint),
            http=provider,
        ),
        mode=SyncMode.INCREMENTAL,
    )
    current_index = build_index(vectors)
    return {
        "mode": mode,
        "provider_identity": validation.identity,
        "initial_upserts": initial_upserts,
        "initial_cursor_advanced": initial_cursor_advanced,
        "top_hit": hits[0].document_id,
        "answer": answer,
        "citations": citations,
        "webhook_verified": True,
        "coalesced_events": len(hints),
        "event_aggregate": hint.aggregate_key,
        "event_poll_upserts": event_changed,
        "event_poll_deletes": event_deleted,
        "scheduled_poll_repairs": polling_changed,
        "scheduled_poll_deletes": polling_deleted,
        "embedded_documents": tuple(embedded),
        "remaining": tuple(sorted(documents)),
        "current_index_documents": current_index.document_ids,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
