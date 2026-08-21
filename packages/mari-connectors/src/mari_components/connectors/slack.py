"""Slack channel/DM history and canonical thread document ingestion."""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import json
import re
from typing import Any, Iterator, Mapping
import urllib.parse

from mari_components.connectors._shared import json_response
from mari_components.connectors.protocol import ValidationResult
from mari_components.errors import AuthenticationFailure, PermanentFailure
from mari_components.http import HttpRequest, HttpTransport
from mari_components.types import DocumentACL, KnowledgeDocument, PollPage, PollRequest, Principal


API = "https://slack.com/api"
MENTION_RE = re.compile(r"<@([A-Z0-9]+)(?:\|[^>]*)?>")
LINK_RE = re.compile(r"<(https?://[^>|]+)(?:\|([^>]*))?>")


@dataclass(frozen=True, slots=True)
class SlackConfig:
    bot_token: str
    channels: tuple[str, ...] = ()
    history_token: str = ""

    def __post_init__(self) -> None:
        if not self.bot_token.strip():
            raise ValueError("Slack bot token is required")


def _call(
    token: str, method: str, params: Mapping[str, Any] | None, *, http: HttpTransport
) -> dict[str, Any]:
    body = urllib.parse.urlencode(params or {}).encode()
    value = json_response(
        http,
        HttpRequest(
            "POST",
            f"{API}/{method}",
            {
                "Authorization": f"Bearer {token.strip()}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body,
        ),
    )
    if not isinstance(value, dict):
        raise PermanentFailure(f"Slack returned invalid data for {method}")
    if not value.get("ok"):
        error = str(value.get("error") or "unknown_error")
        if error in {"invalid_auth", "not_authed", "token_revoked", "account_inactive"}:
            raise AuthenticationFailure(f"Slack rejected credentials: {error}")
        raise PermanentFailure(f"Slack API error on {method}: {error}")
    return value


def validate_slack(config: SlackConfig, *, http: HttpTransport) -> ValidationResult:
    try:
        value = _call(config.bot_token, "auth.test", None, http=http)
    except Exception as error:
        return ValidationResult(False, str(error))
    return ValidationResult(
        True,
        identity=str(value.get("team") or value.get("team_id") or value.get("user") or ""),
    )


def _paginate(
    token: str,
    method: str,
    params: Mapping[str, Any],
    *,
    http: HttpTransport,
    page_limit: int,
    collection: str,
) -> tuple[list[dict], bool]:
    rows: list[dict] = []
    cursor = ""
    for _ in range(page_limit):
        value = _call(
            token,
            method,
            {**params, **({"cursor": cursor} if cursor else {})},
            http=http,
        )
        rows.extend(item for item in value.get(collection) or [] if isinstance(item, dict))
        cursor = str((value.get("response_metadata") or {}).get("next_cursor") or "")
        if not cursor:
            return rows, True
    return rows, False


def _users(config: SlackConfig, request: PollRequest, *, http: HttpTransport) -> dict[str, str]:
    rows, _ = _paginate(
        config.bot_token,
        "users.list",
        {"limit": 200},
        http=http,
        page_limit=request.page_limit,
        collection="members",
    )
    return {
        str(user["id"]): str(
            (user.get("profile") or {}).get("display_name")
            or (user.get("profile") or {}).get("real_name")
            or user.get("name")
            or user["id"]
        )
        for user in rows
        if user.get("id")
    }


def _clean(text: str, users: Mapping[str, str]) -> str:
    value = MENTION_RE.sub(lambda match: "@" + users.get(match.group(1), match.group(1)), text)
    value = LINK_RE.sub(lambda match: match.group(2) or match.group(1), value)
    return (
        value.replace("<!channel>", "@channel")
        .replace("<!here>", "@here")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .strip()
    )


def _message_ts(message: Mapping[str, Any]) -> float:
    values = [message.get("ts"), (message.get("edited") or {}).get("ts"), message.get("latest_reply")]
    parsed: list[float] = []
    for value in values:
        try:
            parsed.append(float(value))
        except (TypeError, ValueError):
            pass
    return max(parsed) if parsed else 0.0


def _thread_document(
    channel: Mapping[str, Any], messages: list[dict], users: Mapping[str, str]
) -> KnowledgeDocument | None:
    readable = [
        message
        for message in messages
        if message.get("type", "message") == "message"
        and message.get("subtype") not in {"message_deleted", "tombstone"}
        and str(message.get("text") or "").strip()
    ]
    if not readable:
        return None
    readable.sort(key=lambda message: float(message.get("ts") or 0))
    root = readable[0]
    root_ts = str(root.get("thread_ts") or root.get("ts") or "")
    channel_id = str(channel.get("id") or "")
    lines: list[str] = []
    for message in readable:
        timestamp = dt.datetime.fromtimestamp(float(message["ts"]), tz=dt.timezone.utc)
        author = users.get(str(message.get("user") or ""), str(message.get("user") or "unknown"))
        lines.append(f"{timestamp:%Y-%m-%d %H:%M} @{author}: {_clean(str(message.get('text') or ''), users)}")
    latest = max(_message_ts(message) for message in readable)
    title = _clean(str(root.get("text") or ""), users)[:120] or f"Slack thread {root_ts}"
    return KnowledgeDocument(
        f"thread:{channel_id}:{root_ts}",
        title,
        "\n".join(lines),
        revision=f"{latest:.6f}",
        updated_at=dt.datetime.fromtimestamp(latest, tz=dt.timezone.utc).isoformat(),
        source_url=f"https://slack.com/archives/{channel_id}/p{root_ts.replace('.', '')}",
        acl=DocumentACL("restricted", (Principal("channel", channel_id),)),
        metadata={"channel": channel_id, "channel_name": str(channel.get("name") or "")},
    )


def fetch_slack_thread(
    config: SlackConfig,
    channel: Mapping[str, Any],
    thread_timestamp: str,
    *,
    users: Mapping[str, str],
    http: HttpTransport,
    page_limit: int = 20,
) -> tuple[KnowledgeDocument | None, bool]:
    token = config.history_token.strip() or config.bot_token.strip()
    rows, complete = _paginate(
        token,
        "conversations.replies",
        {"channel": channel["id"], "ts": thread_timestamp, "limit": 200},
        http=http,
        page_limit=page_limit,
        collection="messages",
    )
    return _thread_document(channel, rows, users), complete


def fetch_slack_thread_by_id(
    config: SlackConfig,
    channel_id: str,
    thread_timestamp: str,
    *,
    http: HttpTransport,
    page_limit: int = 20,
) -> tuple[KnowledgeDocument | None, bool]:
    """Fetch one canonical thread when an event only carries provider IDs.

    Event receivers should treat Slack payloads as dirty hints and call this
    function rather than attempting to construct knowledge from the event
    body.  The complete thread is deterministic and therefore safe to replay.
    """
    if not channel_id.strip() or not thread_timestamp.strip():
        raise ValueError("Slack channel id and thread timestamp are required")
    request = PollRequest(page_limit=page_limit)
    users = _users(config, request, http=http)
    return fetch_slack_thread(
        config,
        {"id": channel_id.strip()},
        thread_timestamp.strip(),
        users=users,
        http=http,
        page_limit=page_limit,
    )


def poll_slack(
    config: SlackConfig, request: PollRequest, *, http: HttpTransport
) -> Iterator[PollPage]:
    users = _users(config, request, http=http)
    channels, channels_complete = _paginate(
        config.bot_token,
        "conversations.list",
        # DMs are bot conversation state, not shared product knowledge. Besides
        # leaking private conversations into the corpus, polling IM/MPIM IDs can
        # make an otherwise healthy source fail when Slack retains a stale DM
        # descriptor that conversations.history answers with channel_not_found.
        {"types": "public_channel,private_channel", "exclude_archived": "true", "limit": 200},
        http=http,
        page_limit=request.page_limit,
        collection="channels",
    )
    wanted = {name.lstrip("#").casefold() for name in config.channels}
    previous = float(request.cursor or 0)
    newest = previous
    documents: list[KnowledgeDocument] = []
    complete = channels_complete
    for channel in channels:
        name = str(channel.get("name") or "")
        if wanted and name.casefold() not in wanted:
            continue
        if not channel.get("is_member"):
            continue
        rows, history_complete = _paginate(
            config.bot_token,
            "conversations.history",
            {
                "channel": channel["id"],
                "limit": 200,
                **({"oldest": f"{previous:.6f}"} if previous else {}),
            },
            http=http,
            page_limit=request.page_limit,
            collection="messages",
        )
        complete = complete and history_complete
        thread_roots: set[str] = set()
        for message in rows:
            newest = max(newest, _message_ts(message))
            if message.get("thread_ts") and message.get("thread_ts") != message.get("ts"):
                thread_roots.add(str(message["thread_ts"]))
                continue
            if int(message.get("reply_count") or 0):
                root_timestamp = str(message.get("ts") or "")
                if root_timestamp:
                    thread_roots.add(root_timestamp)
                continue
            document = _thread_document(channel, [message], users)
            if document is not None:
                documents.append(document)
        # conversations.history returns reply rows independently of their root.
        # Refetch each affected root so polling repairs missed provider events
        # and produces the same deterministic aggregate as event ingestion.
        for root_timestamp in sorted(thread_roots, key=float):
            document, thread_complete = fetch_slack_thread(
                config,
                channel,
                root_timestamp,
                users=users,
                http=http,
                page_limit=request.page_limit,
            )
            if document is not None:
                documents.append(document)
            complete = complete and thread_complete
    yield PollPage(
        tuple(documents),
        next_cursor=f"{newest:.6f}" if complete and newest else request.cursor,
        snapshot_complete=complete,
        provider_metadata={
            "thread_reconciliation": "complete" if complete else "incomplete",
        },
    )
