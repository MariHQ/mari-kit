"""Snapshot Docs → register watch → drain changes → update vector generation."""

from __future__ import annotations

import json
import os
from typing import Iterable, Mapping

import numpy as np

from mari_components.connectors import (
    GoogleDriveConfig, poll_google_drive, start_google_drive_watch,
    validate_google_drive,
)
from mari_components.connectors.events import gdrive_change_hint
from mari_components.retrieval import build_index, search_index
from mari_components.sync import SyncState, plan_sync
from mari_components.types import KnowledgeDocument, PollPage, PollRequest, SyncMode

from examples.support import (
    FakeGoogleDrive, embed_document, required, selected_mode, token_vectors,
    urllib_transport,
)


def _apply_pages(
    pages: Iterable[PollPage],
    state: SyncState,
    documents: dict[str, KnowledgeDocument],
    vectors: dict[str, np.ndarray],
    embedded: list[str],
    *,
    mode: SyncMode,
) -> tuple[SyncState, tuple[str, ...], tuple[str, ...]]:
    changed: list[str] = []
    deleted: list[str] = []
    for page in pages:
        plan = plan_sync(state, page, mode=mode)
        # A real host performs these writes and the state update in its own
        # transaction. ACL/revision-only upserts are persisted without
        # recomputing derived vectors when title and body are unchanged.
        for document in plan.upserts:
            previous = documents.get(document.external_id)
            documents[document.external_id] = document
            if (
                previous is None
                or previous.title != document.title
                or previous.body != document.body
            ):
                vectors[document.external_id] = embed_document(document)
                embedded.append(document.external_id)
            changed.append(document.external_id)
        for tombstone in plan.deletes:
            documents.pop(tombstone.external_id, None)
            vectors.pop(tombstone.external_id, None)
            deleted.append(tombstone.external_id)
        state = plan.state
    return state, tuple(changed), tuple(deleted)


def _headers(value: str) -> dict[str, str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise RuntimeError("GDRIVE_NOTIFICATION_HEADERS_JSON must be valid JSON") from error
    if not isinstance(parsed, dict) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in parsed.items()
    ):
        raise RuntimeError("GDRIVE_NOTIFICATION_HEADERS_JSON must contain string headers")
    return parsed


def run(environment: Mapping[str, str] | None = None) -> dict[str, object]:
    env = os.environ if environment is None else environment
    mode = selected_mode(env)
    config = GoogleDriveConfig(
        required(env, "GDRIVE_ACCESS_TOKEN"), str(env.get("GDRIVE_FOLDER_ID") or "").strip(),
    )
    callback_url = required(env, "GDRIVE_CALLBACK_URL")
    channel_id = required(env, "GDRIVE_CHANNEL_ID")
    channel_token = required(env, "GDRIVE_CHANNEL_TOKEN")
    notification_headers = _headers(required(env, "GDRIVE_NOTIFICATION_HEADERS_JSON"))
    provider = FakeGoogleDrive() if mode == "fake" else urllib_transport

    validation = validate_google_drive(config, http=provider)
    if not validation.ok:
        raise RuntimeError(validation.message)
    documents: dict[str, KnowledgeDocument] = {}
    vectors: dict[str, np.ndarray] = {}
    embedded: list[str] = []
    state, initial_changed, _ = _apply_pages(
        poll_google_drive(config, PollRequest(mode=SyncMode.FULL), http=provider),
        SyncState(), documents, vectors, embedded, mode=SyncMode.FULL,
    )
    if not state.cursor:
        raise RuntimeError("initial Google Drive snapshot returned no Changes cursor")
    initial_index = build_index(vectors)
    previous_doc_one_vector = np.array(vectors.get("doc-1"), copy=True) if "doc-1" in vectors else None

    watch = start_google_drive_watch(
        config,
        state.cursor.removeprefix("changes:"),
        callback_url,
        channel_id,
        channel_token,
        http=provider,
    )
    normalized_headers = {key.casefold(): value for key, value in notification_headers.items()}
    if normalized_headers.get("x-goog-channel-token") != channel_token:
        raise RuntimeError("Google Drive notification channel token does not match")
    hint = gdrive_change_hint(notification_headers)

    if mode == "fake":
        provider.publish_changes()
    state, changed, deleted = _apply_pages(
        poll_google_drive(
            config,
            PollRequest(SyncMode.INCREMENTAL, state.cursor, state.checkpoint),
            http=provider,
        ),
        state, documents, vectors, embedded, mode=SyncMode.INCREMENTAL,
    )
    current_index = build_index(vectors)
    hits = search_index(current_index, token_vectors("retention ninety"), limit=1)
    current_doc_one_vector = vectors.get("doc-1")
    vector_changed = (
        previous_doc_one_vector is not None
        and current_doc_one_vector is not None
        and not np.array_equal(previous_doc_one_vector, current_doc_one_vector)
    )
    return {
        "mode": mode,
        "provider_identity": validation.identity,
        "initial_documents": initial_changed,
        "watch_resource": watch.resource_id,
        "notification_aggregate": hint.aggregate_key,
        "changed_documents": changed,
        "deleted_documents": deleted,
        "embedded_documents": tuple(embedded),
        "embedding_changed_for_edit": vector_changed,
        "deleted_vector_removed": "doc-2" not in vectors,
        "acl_only_change_not_reembedded": embedded.count("doc-4") == 1,
        "acl_only_change_persisted": any(
            principal.identifier == "product@example.com"
            for principal in documents["doc-4"].acl.principals
        ),
        "initial_index_documents": initial_index.document_ids,
        "current_index_documents": current_index.document_ids,
        "top_hit_after_edit": hits[0].document_id,
        "cursor": state.cursor,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
