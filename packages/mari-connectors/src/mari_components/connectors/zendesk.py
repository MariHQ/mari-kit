"""Zendesk Guide article ingestion with bounded page checkpoints."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Iterator
import urllib.parse

from mari_components.connectors._shared import json_response
from mari_components.connectors.protocol import ValidationResult
from mari_components.http import HttpRequest, HttpTransport
from mari_components.types import DocumentACL, KnowledgeDocument, PollPage, PollRequest


@dataclass(frozen=True, slots=True)
class ZendeskConfig:
    subdomain: str
    email: str
    api_token: str


def _base(config: ZendeskConfig) -> str:
    subdomain = config.subdomain.strip().removeprefix("https://").removeprefix("http://").split(".")[0]
    if not subdomain or not config.email.strip() or not config.api_token.strip():
        raise ValueError("Zendesk subdomain, email, and API token are required")
    return f"https://{subdomain}.zendesk.com"


def _headers(config: ZendeskConfig) -> dict[str, str]:
    raw = f"{config.email.strip()}/token:{config.api_token.strip()}"
    return {"Authorization": "Basic " + base64.b64encode(raw.encode()).decode(), "Accept": "application/json"}


def validate_zendesk(config: ZendeskConfig, *, http: HttpTransport) -> ValidationResult:
    try:
        value = json_response(http, HttpRequest("GET", _base(config) + "/api/v2/users/me.json", _headers(config)))
    except Exception as error:
        return ValidationResult(False, str(error))
    user = value.get("user") or {}
    return ValidationResult(True, identity=str(user.get("email") or user.get("name") or ""))


def poll_zendesk(config: ZendeskConfig, request: PollRequest, *, http: HttpTransport) -> Iterator[PollPage]:
    page_number = int(request.checkpoint or 1)
    newest = str(request.cursor or "")
    for _ in range(request.page_limit):
        query = urllib.parse.urlencode({"page": page_number, "per_page": request.page_size, "sort_by": "updated_at", "sort_order": "asc"})
        value = json_response(http, HttpRequest("GET", _base(config) + "/api/v2/help_center/articles.json?" + query, _headers(config)))
        documents: list[KnowledgeDocument] = []
        for article in value.get("articles") or []:
            updated = str(article.get("updated_at") or "")
            newest = max(newest, updated)
            if request.cursor and updated <= request.cursor:
                continue
            article_id = str(article.get("id") or "")
            documents.append(
                KnowledgeDocument(
                    f"article:{article_id}",
                    str(article.get("title") or article_id),
                    str(article.get("body") or ""),
                    revision=updated,
                    updated_at=updated,
                    source_url=str(article.get("html_url") or ""),
                    acl=DocumentACL("connector_scope"),
                    metadata={"locale": str(article.get("locale") or "")},
                )
            )
        terminal = not bool(value.get("next_page"))
        page_number += 1
        yield PollPage(tuple(documents), next_cursor=newest if terminal else request.cursor, next_checkpoint=None if terminal else str(page_number), snapshot_complete=terminal)
        if terminal:
            return
    yield PollPage(next_cursor=request.cursor, next_checkpoint=str(page_number), snapshot_complete=False, provider_metadata={"reason": "page_limit"})
