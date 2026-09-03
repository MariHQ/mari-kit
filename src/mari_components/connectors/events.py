"""Pure verification and bounded change-hint parsing for provider events."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse
from collections.abc import Mapping
from typing import Any

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


def verify_hmac_sha256(
    raw: bytes, supplied: str, secret: str, *, prefix: str = "sha256="
) -> None:
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
        raise AuthenticationFailure(
            "Slack event timestamp is outside the replay window"
        )
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
    return ChangeHint(
        provider="github",
        aggregate_key=f"repository:{full_name.casefold()}",
        event_type=event[:80],
        metadata=metadata,
    )


def confluence_change_hint(payload: Mapping[str, Any]) -> ChangeHint:
    content = _object(payload.get("page") or payload.get("content"))
    space = _object(content.get("space") or payload.get("space"))
    event = str(payload.get("webhookEvent") or payload.get("event") or "")[:120]
    page_id = str(content.get("id") or payload.get("pageId") or "")[:200]
    space_key = str(space.get("key") or payload.get("spaceKey") or "")[:200]
    if not event or (not page_id and not space_key):
        raise PermanentFailure("Confluence event and page or space are required")
    deleted = any(
        word in event.casefold() for word in ("removed", "deleted", "trashed")
    )
    aggregate = f"page:{page_id}" if page_id else f"space:{space_key}"
    return ChangeHint(
        provider="confluence",
        aggregate_key=aggregate,
        event_type=event,
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
        provider="gdrive",
        aggregate_key=f"channel:{channel_id}",
        event_type=state,
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
        provider="slack",
        aggregate_key=f"thread:{channel}:{thread_ts}",
        event_type=subtype or event_type,
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


def gitlab_change_hint(payload: Mapping[str, Any]) -> ChangeHint:
    project = _object(payload.get("project"))
    project_path = str(project.get("path_with_namespace") or "")[:300]
    event_type = str(payload.get("object_kind") or payload.get("event_name") or "")[:80]
    if not project_path or not event_type:
        raise PermanentFailure("GitLab event and project are required")
    attributes = _object(payload.get("object_attributes"))
    external_id = str(attributes.get("id") or attributes.get("iid") or "")[:200]
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
    return ChangeHint(
        provider="gitlab",
        aggregate_key=f"project:{project_path.casefold()}",
        event_type=event_type,
        external_id=external_id,
        revision=str(payload.get("after") or attributes.get("updated_at") or "")[:200],
        metadata={
            "project": project_path,
            "ref": str(payload.get("ref") or "")[:500],
            "paths": tuple(paths),
            "paths_truncated": len(paths) >= MAX_DIRTY_PATHS,
        },
    )


def box_change_hint(payload: Mapping[str, Any]) -> ChangeHint:
    source = _object(payload.get("source"))
    item_id = str(source.get("id") or "")[:200]
    event_type = str(payload.get("trigger") or payload.get("event_type") or "")[:100]
    if not item_id or not event_type:
        raise PermanentFailure("Box event source and trigger are required")
    deleted = event_type.casefold() in {"trash", "delete", "file.trash", "file.delete"}
    return ChangeHint(
        provider="box",
        aggregate_key=f"item:{item_id}",
        event_type=event_type,
        external_id=item_id,
        revision=str(source.get("sha1") or source.get("etag") or "")[:200],
        deleted=deleted,
        metadata={"item_type": str(source.get("type") or "")[:80]},
    )


def microsoft_graph_change_hint(
    payload: Mapping[str, Any], *, provider: str
) -> ChangeHint:
    notifications = payload.get("value")
    if not isinstance(notifications, list) or not notifications:
        raise PermanentFailure("Microsoft Graph event contains no notifications")
    first = _object(notifications[0])
    resource_data = _object(first.get("resourceData"))
    subscription = str(first.get("subscriptionId") or "")[:200]
    resource = str(first.get("resource") or "")[:1000]
    item_id = str(resource_data.get("id") or "")[:200]
    if not subscription or not resource:
        raise PermanentFailure("Microsoft Graph notification is incomplete")
    return ChangeHint(
        provider=provider,
        aggregate_key=f"subscription:{subscription}",
        event_type=str(first.get("changeType") or "changed")[:80],
        external_id=item_id,
        revision=str(resource_data.get("@odata.etag") or "")[:200],
        deleted=str(first.get("changeType") or "").casefold() == "deleted",
        metadata={"resource": resource, "notification_count": len(notifications)},
    )


def object_storage_change_hint(
    payload: Mapping[str, Any], *, provider: str
) -> ChangeHint:
    keys: list[str] = []
    container = ""
    event_type = "changed"
    revision = ""
    deleted = False
    if provider == "s3":
        records = payload.get("Records")
        if not isinstance(records, list) or not records:
            raise PermanentFailure("S3 event contains no records")
        for record in records[:MAX_DIRTY_PATHS]:
            value = _object(record)
            s3 = _object(value.get("s3"))
            container = container or str(_object(s3.get("bucket")).get("name") or "")
            object_data = _object(s3.get("object"))
            key = urllib.parse.unquote_plus(str(object_data.get("key") or ""))[:1000]
            if key:
                keys.append(key)
            event_type = str(value.get("eventName") or event_type)
            revision = str(
                object_data.get("versionId") or object_data.get("eTag") or revision
            )
        deleted = "remove" in event_type.casefold()
    elif provider == "gcs":
        container = str(payload.get("bucket") or "")
        key = str(payload.get("name") or "")[:1000]
        keys = [key] if key else []
        event_type = str(payload.get("type") or payload.get("eventType") or event_type)
        revision = str(payload.get("generation") or payload.get("etag") or "")
        deleted = "delete" in event_type.casefold()
    elif provider == "azure_blob":
        data = _object(payload.get("data"))
        subject = str(payload.get("subject") or "")
        parts = subject.split("/blobs/", 1)
        container = parts[0].rsplit("/containers/", 1)[-1] if parts else ""
        keys = [parts[1]] if len(parts) == 2 and parts[1] else []
        event_type = str(payload.get("eventType") or event_type)
        revision = str(data.get("eTag") or "")
        deleted = "deleted" in event_type.casefold()
    else:
        raise ValueError(f"unsupported object-storage provider: {provider!r}")
    if not container:
        raise PermanentFailure("object-storage event has no container")
    return ChangeHint(
        provider=provider,
        aggregate_key=f"container:{container}",
        event_type=event_type[:120],
        external_id=keys[0][:1000] if len(keys) == 1 else "",
        revision=revision[:200],
        deleted=deleted and len(keys) == 1,
        metadata={"container": container[:300], "keys": tuple(keys)},
    )


def cloudevent_change_hint(payload: Mapping[str, Any]) -> ChangeHint:
    event_id = str(payload.get("id") or "")[:300]
    source = str(payload.get("source") or "")[:1000]
    event_type = str(payload.get("type") or "")[:300]
    subject = str(payload.get("subject") or "")[:1000]
    if not event_id or not source or not event_type:
        raise PermanentFailure("CloudEvent requires id, source, and type")
    data = _object(payload.get("data"))
    deleted = any(value in event_type.casefold() for value in ("deleted", "removed"))
    return ChangeHint(
        provider="cloudevents",
        aggregate_key=f"{source}:{subject or event_id}",
        event_type=event_type,
        external_id=subject,
        revision=str(data.get("revision") or data.get("etag") or "")[:200],
        deleted=deleted,
        metadata={"event_id": event_id, "source": source},
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
