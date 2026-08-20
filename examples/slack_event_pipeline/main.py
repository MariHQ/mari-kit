"""Poll Slack → process event hint → poll again to repair a missed event."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Iterable, Mapping

from mari_components.connectors import (
    SlackConfig, fetch_slack_thread_by_id, poll_slack, validate_slack,
)
from mari_components.connectors.events import (
    coalesce_hints, parse_json_object, slack_change_hint, verify_slack_signature,
)
from mari_components.sync import SyncState, plan_sync
from mari_components.types import KnowledgeDocument, PollPage, PollRequest, SyncMode

from examples.support import FakeSlack, required, selected_mode, urllib_transport


def _fake_event(secret: str, request_timestamp: str) -> tuple[bytes, str]:
    raw = json.dumps({
        "event_id": "Ev-example",
        "event": {
            "type": "message", "channel": "C-ENG", "ts": "102.000001",
            "thread_ts": "100.000001", "user": "U1",
        },
    }, separators=(",", ":")).encode()
    signature = "v0=" + hmac.new(
        secret.encode(), b"v0:" + request_timestamp.encode() + b":" + raw, hashlib.sha256,
    ).hexdigest()
    return raw, signature


def _apply(
    state: SyncState,
    documents: dict[str, KnowledgeDocument],
    pages: Iterable[PollPage],
    *,
    mode: SyncMode,
) -> tuple[SyncState, tuple[str, ...], tuple[str, ...]]:
    changed: list[str] = []
    unchanged: list[str] = []
    for page in pages:
        plan = plan_sync(state, page, mode=mode)
        for document in plan.upserts:
            documents[document.external_id] = document
            changed.append(document.external_id)
        for tombstone in plan.deletes:
            documents.pop(tombstone.external_id, None)
        unchanged.extend(plan.unchanged)
        state = plan.state
    return state, tuple(changed), tuple(unchanged)


def run(environment: Mapping[str, str] | None = None) -> dict[str, object]:
    env = os.environ if environment is None else environment
    mode = selected_mode(env)
    bot_token = required(env, "SLACK_BOT_TOKEN")
    signing_secret = required(env, "SLACK_SIGNING_SECRET")
    request_timestamp = required(env, "SLACK_REQUEST_TIMESTAMP")
    channel_name = required(env, "SLACK_CHANNELS")
    config = SlackConfig(
        bot_token,
        tuple(value.strip() for value in channel_name.split(",") if value.strip()),
        str(env.get("SLACK_HISTORY_TOKEN") or "").strip(),
    )
    if mode == "fake":
        provider = FakeSlack()
        now = float(request_timestamp)
    else:
        provider = urllib_transport
        now = None
    validation = validate_slack(config, http=provider)
    if not validation.ok:
        raise RuntimeError(validation.message)

    documents: dict[str, KnowledgeDocument] = {}
    state, initial_changed, _ = _apply(
        SyncState(), documents,
        poll_slack(config, PollRequest(mode=SyncMode.FULL), http=provider),
        mode=SyncMode.FULL,
    )
    initial_messages = next(iter(documents.values())).body.count("\n") + 1

    if mode == "fake":
        provider.add_reply("Events deliver this reply immediately.")
        raw, signature = _fake_event(signing_secret, request_timestamp)
    else:
        raw = required(env, "SLACK_EVENT_JSON").encode()
        signature = required(env, "SLACK_SIGNATURE")
    verify_slack_signature(raw, request_timestamp, signature, signing_secret, now=now)
    hint = slack_change_hint(parse_json_object(raw))
    hints = coalesce_hints((hint, hint))
    streamed, complete = fetch_slack_thread_by_id(
        config,
        str(hint.metadata["channel"]),
        str(hint.metadata["thread_timestamp"]),
        http=provider,
    )
    if streamed is None:
        raise RuntimeError("Slack thread contains no readable messages")
    # Event refetch updates the manifest but deliberately preserves the polling
    # cursor. Provider events and polling have independent progress semantics.
    state, stream_changed, _ = _apply(
        state,
        documents,
        (PollPage(
            (streamed,), next_cursor=state.cursor, snapshot_complete=complete,
        ),),
        mode=SyncMode.INCREMENTAL,
    )
    stream_messages = streamed.body.count("\n") + 1

    # Simulate one lost event. The next scheduled poll sees the reply row,
    # refetches its root thread, and repairs the same canonical document.
    if mode == "fake":
        provider.add_reply("Polling repairs this reply when its event is lost.")
    state, polling_changed, polling_unchanged = _apply(
        state,
        documents,
        poll_slack(
            config,
            PollRequest(SyncMode.INCREMENTAL, state.cursor, state.checkpoint),
            http=provider,
        ),
        mode=SyncMode.INCREMENTAL,
    )
    final = documents[streamed.external_id]
    allowed_channel = required(env, "SLACK_ALLOWED_CHANNEL")
    can_read = any(
        principal.kind == "channel" and principal.identifier == allowed_channel
        for principal in final.acl.principals
    )
    return {
        "mode": mode,
        "provider_identity": validation.identity,
        "initial_polled_documents": initial_changed,
        "initial_messages": initial_messages,
        "signature_verified": True,
        "coalesced_events": len(hints),
        "stream_updated_documents": stream_changed,
        "stream_messages": stream_messages,
        "polling_repaired_documents": polling_changed,
        "polling_unchanged_documents": polling_unchanged,
        "final_messages": final.body.count("\n") + 1,
        "poll_cursor": state.cursor,
        "thread_id": final.external_id,
        "visibility": final.acl.visibility,
        "authorized": can_read,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
