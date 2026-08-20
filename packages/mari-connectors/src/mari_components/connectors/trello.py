"""Trello board/list/card snapshot ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Mapping
import urllib.parse

from mari_components.connectors._shared import json_response
from mari_components.connectors.protocol import ValidationResult
from mari_components.http import HttpRequest, HttpTransport
from mari_components.types import DocumentACL, KnowledgeDocument, PollPage, PollRequest


API = "https://api.trello.com/1"


@dataclass(frozen=True, slots=True)
class TrelloConfig:
    api_key: str
    token: str


def _get(config: TrelloConfig, path: str, params: Mapping[str, Any], *, http: HttpTransport) -> Any:
    if not config.api_key.strip() or not config.token.strip():
        raise ValueError("Trello API key and token are required")
    query = urllib.parse.urlencode({**params, "key": config.api_key.strip(), "token": config.token.strip()})
    return json_response(http, HttpRequest("GET", API + path + "?" + query))


def validate_trello(config: TrelloConfig, *, http: HttpTransport) -> ValidationResult:
    try:
        value = _get(config, "/members/me", {"fields": "id,username,fullName"}, http=http)
    except Exception as error:
        return ValidationResult(False, str(error))
    return ValidationResult(True, identity=str(value.get("username") or value.get("fullName") or ""))


def poll_trello(config: TrelloConfig, request: PollRequest, *, http: HttpTransport) -> Iterator[PollPage]:
    boards = _get(config, "/members/me/boards", {"filter": "open", "fields": "id,name,dateLastActivity,url"}, http=http)
    documents: list[KnowledgeDocument] = []
    newest = str(request.cursor or "")
    for board in boards:
        updated = str(board.get("dateLastActivity") or "")
        newest = max(newest, updated)
        if request.cursor and updated <= request.cursor:
            continue
        board_id = str(board.get("id") or "")
        lists = _get(config, f"/boards/{urllib.parse.quote(board_id, safe='')}/lists", {"filter": "open", "fields": "id,name"}, http=http)
        cards = _get(config, f"/boards/{urllib.parse.quote(board_id, safe='')}/cards", {"filter": "open", "fields": "id,name,desc,idList,due,url"}, http=http)
        names = {str(item.get("id") or ""): str(item.get("name") or "") for item in lists}
        lines: list[str] = []
        for card in cards:
            lines.append(f"## {card.get('name') or card.get('id')}\nList: {names.get(str(card.get('idList') or ''), '')}\nDue: {card.get('due') or ''}\n\n{card.get('desc') or ''}")
        documents.append(
            KnowledgeDocument(
                f"board:{board_id}",
                str(board.get("name") or board_id),
                "\n\n".join(lines),
                revision=updated or str(len(cards)),
                updated_at=updated,
                source_url=str(board.get("url") or ""),
                acl=DocumentACL("connector_scope"),
                metadata={"cards": len(cards)},
            )
        )
    yield PollPage(tuple(documents), next_cursor=newest, snapshot_complete=True)
