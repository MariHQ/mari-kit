"""Notion page search and bounded block-tree ingestion."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterator
import urllib.parse

from mari_components.connectors._shared import json_response
from mari_components.connectors.protocol import ValidationResult
from mari_components.http import HttpRequest, HttpTransport
from mari_components.types import DocumentACL, KnowledgeDocument, PollPage, PollRequest


API = "https://api.notion.com/v1"


@dataclass(frozen=True, slots=True)
class NotionConfig:
    token: str


def _request(config: NotionConfig, method: str, path: str, body: dict | None, *, http: HttpTransport) -> dict:
    if not config.token.strip():
        raise ValueError("Notion token is required")
    value = json_response(
        http,
        HttpRequest(
            method,
            API + path,
            {"Authorization": f"Bearer {config.token.strip()}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"},
            json.dumps(body).encode() if body is not None else None,
        ),
    )
    return value if isinstance(value, dict) else {}


def validate_notion(config: NotionConfig, *, http: HttpTransport) -> ValidationResult:
    try:
        value = _request(config, "GET", "/users/me", None, http=http)
    except Exception as error:
        return ValidationResult(False, str(error))
    return ValidationResult(True, identity=str(value.get("name") or value.get("id") or ""))


def _rich_text(values: Any) -> str:
    return "".join(str(item.get("plain_text") or "") for item in (values or []) if isinstance(item, dict))


def _title(page: dict) -> str:
    for value in (page.get("properties") or {}).values():
        if value.get("type") == "title":
            return _rich_text(value.get("title"))
    return "Untitled"


def _blocks(config: NotionConfig, block_id: str, request: PollRequest, *, http: HttpTransport, depth: int = 0) -> tuple[str, bool]:
    cursor = ""
    lines: list[str] = []
    complete = True
    for _ in range(request.page_limit):
        query = urllib.parse.urlencode({"page_size": request.page_size, **({"start_cursor": cursor} if cursor else {})})
        value = _request(config, "GET", f"/blocks/{urllib.parse.quote(block_id, safe='')}/children?{query}", None, http=http)
        for block in value.get("results") or []:
            kind = str(block.get("type") or "")
            content = block.get(kind) or {}
            text = _rich_text(content.get("rich_text"))
            if kind.startswith("heading_"):
                level = kind.removeprefix("heading_")
                prefix = "#" * (int(level) if level.isdigit() else 2)
                lines.append(f"{prefix} {text}")
            elif kind in {"bulleted_list_item", "numbered_list_item", "to_do"}:
                lines.append(f"- {text}")
            elif text:
                lines.append(text)
            if block.get("has_children") and depth < 1:
                child, child_complete = _blocks(config, str(block.get("id") or ""), request, http=http, depth=depth + 1)
                if child:
                    lines.append(child)
                complete = complete and child_complete
        cursor = str(value.get("next_cursor") or "")
        if not value.get("has_more") or not cursor:
            return "\n".join(lines), complete
    return "\n".join(lines), False


def poll_notion(config: NotionConfig, request: PollRequest, *, http: HttpTransport) -> Iterator[PollPage]:
    cursor = str(request.checkpoint or "")
    newest = str(request.cursor or "")
    for _ in range(request.page_limit):
        value = _request(
            config,
            "POST",
            "/search",
            {"filter": {"property": "object", "value": "page"}, "sort": {"direction": "ascending", "timestamp": "last_edited_time"}, "page_size": request.page_size, **({"start_cursor": cursor} if cursor else {})},
            http=http,
        )
        documents: list[KnowledgeDocument] = []
        page_complete = True
        for page in value.get("results") or []:
            updated = str(page.get("last_edited_time") or "")
            newest = max(newest, updated)
            if request.cursor and updated <= request.cursor:
                continue
            body, blocks_complete = _blocks(config, str(page.get("id") or ""), request, http=http)
            page_complete = page_complete and blocks_complete
            documents.append(
                KnowledgeDocument(
                    str(page.get("id") or ""),
                    _title(page),
                    body,
                    revision=updated,
                    updated_at=updated,
                    source_url=str(page.get("url") or ""),
                    acl=DocumentACL("connector_scope"),
                )
            )
        cursor = str(value.get("next_cursor") or "")
        terminal = not bool(value.get("has_more")) and page_complete
        yield PollPage(tuple(documents), next_cursor=newest if terminal else request.cursor, next_checkpoint=None if terminal else cursor, snapshot_complete=terminal)
        if terminal:
            return
        if not cursor:
            return
    yield PollPage(next_cursor=request.cursor, next_checkpoint=cursor, snapshot_complete=False, provider_metadata={"reason": "page_limit"})
