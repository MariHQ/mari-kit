"""Trello board/list/card snapshot ingestion."""

from __future__ import annotations

import urllib.parse
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from mari_components.connectors._shared import json_response
from mari_components.connectors.protocol import ValidationResult
from mari_components.http import HttpRequest, HttpTransport
from mari_components.types import (
    KnowledgeDocument,
    PollPage,
    PollRequest,
    content_revision,
)

API = "https://api.trello.com/1"


@dataclass(frozen=True, slots=True)
class TrelloConfig:
    api_key: str = field(repr=False)
    token: str = field(repr=False)


def _get(
    config: TrelloConfig, path: str, params: Mapping[str, Any], *, http: HttpTransport
) -> Any:
    if not config.api_key.strip() or not config.token.strip():
        raise ValueError("Trello API key and token are required")
    query = urllib.parse.urlencode(
        {**params, "key": config.api_key.strip(), "token": config.token.strip()}
    )
    return json_response(http, HttpRequest("GET", API + path + "?" + query))


def validate_trello(config: TrelloConfig, *, http: HttpTransport) -> ValidationResult:
    try:
        value = _get(
            config, "/members/me", {"fields": "id,username,fullName"}, http=http
        )
    except Exception as error:
        return ValidationResult(False, str(error))
    return ValidationResult(
        True, identity=str(value.get("username") or value.get("fullName") or "")
    )


def poll_trello(
    config: TrelloConfig, request: PollRequest, *, http: HttpTransport
) -> Iterator[PollPage]:
    boards = _get(
        config,
        "/members/me/boards",
        {"filter": "open", "fields": "id,name,dateLastActivity,url"},
        http=http,
    )
    documents: list[KnowledgeDocument] = []
    newest = str(request.cursor or "")
    for board in boards:
        updated = str(board.get("dateLastActivity") or "")
        newest = max(newest, updated)
        if request.cursor and updated <= request.cursor:
            continue
        board_id = str(board.get("id") or "")
        lists = _get(
            config,
            f"/boards/{urllib.parse.quote(board_id, safe='')}/lists",
            {"filter": "open", "fields": "id,name"},
            http=http,
        )
        cards = _get(
            config,
            f"/boards/{urllib.parse.quote(board_id, safe='')}/cards",
            {"filter": "open", "fields": "id,name,desc,idList,due,url"},
            http=http,
        )
        names = {
            str(item.get("id") or ""): str(item.get("name") or "") for item in lists
        }
        lines: list[str] = []
        for card in cards:
            lines.append(
                f"## {card.get('name') or card.get('id')}\nList: {names.get(str(card.get('idList') or ''), '')}\nDue: {card.get('due') or ''}\n\n{card.get('desc') or ''}"
            )
        content = "\n\n".join(lines)
        provider_revision = updated or str(len(cards))
        documents.append(
            KnowledgeDocument(
                source_id="trello",
                external_id=f"board:{board_id}",
                title=str(board.get("name") or board_id),
                body=content,
                revision=content_revision(content),
                provider_revision=provider_revision,
                updated_at=updated,
                source_url=str(board.get("url") or ""),
                metadata={"cards": len(cards)},
            )
        )
    yield PollPage(upserts=tuple(documents), next_cursor=newest, snapshot_complete=True)
