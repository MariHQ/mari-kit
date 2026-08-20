"""Pure verification and bounded change-hint parsing for provider events."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Mapping

from mari_components.errors import AuthenticationFailure, PermanentFailure
from mari_components.types import ChangeHint


MAX_DIRTY_PATHS = 500


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def parse_json_object(raw: bytes, *, maximum_bytes: int = 1_048_576) -> dict[str, Any]:
    if len(raw) > maximum_bytes:
        raise PermanentFailure("provider event exceeds the configured size limit")
    try:
        value = json.loads(raw or b"{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PermanentFailure("provider event contains invalid JSON") from error
    if not isinstance(value, dict):
        raise PermanentFailure("provider event must be a JSON object")
    return value


def verify_hmac_sha256(raw: bytes, supplied: str, secret: str, *, prefix: str = "sha256=") -> None:
    if not secret or not supplied.startswith(prefix):
        raise AuthenticationFailure("provider event signature is missing or invalid")
    expected = prefix + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied):
        raise AuthenticationFailure("provider event signature is invalid")


def verify_slack_signature(
    raw: bytes,
    timestamp: str,
    supplied: str,
    secret: str,
    *,
    now: float | None = None,
    tolerance_seconds: int = 300,
) -> None:
    try:
        event_time = int(timestamp)
    except (TypeError, ValueError):
        raise AuthenticationFailure("Slack timestamp is invalid") from None
    current = time.time() if now is None else now
    if abs(current - event_time) > tolerance_seconds:
        raise AuthenticationFailure("Slack event timestamp is outside the replay window")
    base = b"v0:" + str(timestamp).encode() + b":" + raw
    expected = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied):
        raise AuthenticationFailure("Slack event signature is invalid")


def github_change_hint(event: str, payload: Mapping[str, Any]) -> ChangeHint:
    repository = _object(payload.get("repository"))
    full_name = str(repository.get("full_name") or "")[:300]
    if not event or not full_name:
        raise PermanentFailure("GitHub event and repository are required")
    metadata: dict[str, Any] = {"action": str(payload.get("action") or "")[:80]}
    issue = _object(payload.get("issue"))
    pull = _object(payload.get("pull_request"))
    number = issue.get("number") or pull.get("number") or payload.get("number")
    if number is not None:
        try:
            metadata["number"] = int(number)
        except (TypeError, ValueError):
            pass
    if event == "push":
        paths: list[str] = []
        for commit in list(payload.get("commits") or [])[:250]:
            if not isinstance(commit, dict):
                continue
            for key in ("added", "modified", "removed"):
                for value in list(commit.get(key) or []):
                    path = str(value)[:1000]
                    if path and path not in paths:
                        paths.append(path)
                    if len(paths) >= MAX_DIRTY_PATHS:
                        break
                if len(paths) >= MAX_DIRTY_PATHS:
                    break
            if len(paths) >= MAX_DIRTY_PATHS:
                break
        metadata.update(
            paths=tuple(paths),
            paths_truncated=len(paths) >= MAX_DIRTY_PATHS,
            ref=str(payload.get("ref") or "")[:500],
        )
    return ChangeHint("github", f"repository:{full_name.casefold()}", event[:80], metadata=metadata)


def confluence_change_hint(payload: Mapping[str, Any]) -> ChangeHint:
    content = _object(payload.get("page") or payload.get("content"))
    space = _object(content.get("space") or payload.get("space"))
    event = str(payload.get("webhookEvent") or payload.get("event") or "")[:120]
    page_id = str(content.get("id") or payload.get("pageId") or "")[:200]
    space_key = str(space.get("key") or payload.get("spaceKey") or "")[:200]
    if not event or (not page_id and not space_key):
        raise PermanentFailure("Confluence event and page or space are required")
    deleted = any(word in event.casefold() for word in ("removed", "deleted", "trashed"))
    aggregate = f"page:{page_id}" if page_id else f"space:{space_key}"
    return ChangeHint(
        "confluence",
        aggregate,
        event,
        external_id=page_id,
        deleted=deleted,
        metadata={"space_key": space_key},
    )


def gdrive_change_hint(headers: Mapping[str, str]) -> ChangeHint:
    normalized = {key.casefold(): value.strip() for key, value in headers.items()}
    channel_id = normalized.get("x-goog-channel-id", "")
    resource_id = normalized.get("x-goog-resource-id", "")
    state = normalized.get("x-goog-resource-state", "").casefold()
    number = normalized.get("x-goog-message-number", "")
    if not channel_id or not resource_id or state not in {"sync", "change", "changed"}:
        raise PermanentFailure("Google Drive notification headers are incomplete")
    try:
        message_number = int(number)
        if message_number < 1:
            raise ValueError
    except ValueError:
        raise PermanentFailure("Google Drive message number is invalid") from None
    return ChangeHint(
        "gdrive",
        f"channel:{channel_id}",
        state,
        revision=str(message_number),
        metadata={"resource_id": resource_id, "message_number": message_number},
    )


def slack_change_hint(payload: Mapping[str, Any]) -> ChangeHint:
    event = _object(payload.get("event"))
    event_type = str(event.get("type") or "")
    channel = str(event.get("channel") or "")
    timestamp = str(event.get("ts") or event.get("event_ts") or "")
    thread_ts = str(event.get("thread_ts") or timestamp)
    if event_type not in {"message", "app_mention"} or not channel or not timestamp:
        raise PermanentFailure("Slack event does not identify a supported message")
    subtype = str(event.get("subtype") or "")
    deleted = subtype in {"message_deleted", "tombstone"}
    return ChangeHint(
        "slack",
        f"thread:{channel}:{thread_ts}",
        subtype or event_type,
        external_id=f"{channel}:{timestamp}",
        revision=str(event.get("edited", {}).get("ts") or timestamp),
        deleted=deleted,
        metadata={
            "channel": channel,
            "timestamp": timestamp,
            "thread_timestamp": thread_ts,
            "user": str(event.get("user") or ""),
        },
    )


def coalesce_hints(hints: list[ChangeHint]) -> tuple[ChangeHint, ...]:
    """Keep the newest hint per aggregate key while preserving first-key order."""
    order: list[tuple[str, str]] = []
    latest: dict[tuple[str, str], ChangeHint] = {}
    for hint in hints:
        key = (hint.provider, hint.aggregate_key)
        if key not in latest:
            order.append(key)
        latest[key] = hint
    return tuple(latest[key] for key in order)
