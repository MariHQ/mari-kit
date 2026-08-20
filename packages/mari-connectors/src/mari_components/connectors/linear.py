"""Linear issue/comment ingestion through its GraphQL API."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterator

from mari_components.connectors._shared import json_response
from mari_components.connectors.protocol import ValidationResult
from mari_components.errors import PermanentFailure
from mari_components.http import HttpRequest, HttpTransport
from mari_components.types import DocumentACL, KnowledgeDocument, PollPage, PollRequest


API = "https://api.linear.app/graphql"


@dataclass(frozen=True, slots=True)
class LinearConfig:
    api_key: str
    team_id: str = ""


def _query(config: LinearConfig, query: str, variables: dict[str, Any], *, http: HttpTransport) -> dict:
    if not config.api_key.strip():
        raise ValueError("Linear API key is required")
    value = json_response(
        http,
        HttpRequest(
            "POST",
            API,
            {"Authorization": config.api_key.strip(), "Content-Type": "application/json"},
            json.dumps({"query": query, "variables": variables}).encode(),
        ),
    )
    if value.get("errors"):
        raise PermanentFailure("Linear GraphQL request failed")
    return value.get("data") or {}


def validate_linear(config: LinearConfig, *, http: HttpTransport) -> ValidationResult:
    try:
        value = _query(config, "query { viewer { id name email } }", {}, http=http).get("viewer") or {}
    except Exception as error:
        return ValidationResult(False, str(error))
    return ValidationResult(True, identity=str(value.get("email") or value.get("name") or ""))


def poll_linear(config: LinearConfig, request: PollRequest, *, http: HttpTransport) -> Iterator[PollPage]:
    query = """query Issues($after:String,$first:Int!,$filter:IssueFilter) {
      issues(after:$after,first:$first,filter:$filter,orderBy:updatedAt) {
        nodes { id identifier title description updatedAt url state { name }
          comments(first:50) { nodes { body user { name } createdAt } } }
        pageInfo { hasNextPage endCursor }
      }
    }"""
    after = str(request.checkpoint or "") or None
    newest = str(request.cursor or "")
    for _ in range(request.page_limit):
        filters: dict[str, Any] = {}
        if config.team_id:
            filters["team"] = {"id": {"eq": config.team_id}}
        if request.cursor:
            filters["updatedAt"] = {"gt": request.cursor}
        connection = _query(config, query, {"after": after, "first": request.page_size, "filter": filters or None}, http=http).get("issues") or {}
        documents: list[KnowledgeDocument] = []
        for issue in connection.get("nodes") or []:
            updated = str(issue.get("updatedAt") or "")
            newest = max(newest, updated)
            body = str(issue.get("description") or "")
            for comment in (issue.get("comments") or {}).get("nodes") or []:
                body += f"\n\nComment by {(comment.get('user') or {}).get('name', 'unknown')}:\n{comment.get('body') or ''}"
            documents.append(
                KnowledgeDocument(
                    str(issue.get("id") or issue.get("identifier") or ""),
                    f"{issue.get('identifier') or ''}: {issue.get('title') or ''}".strip(": "),
                    body.strip(),
                    revision=updated,
                    updated_at=updated,
                    source_url=str(issue.get("url") or ""),
                    acl=DocumentACL("connector_scope"),
                    metadata={"state": str((issue.get("state") or {}).get("name") or "")},
                )
            )
        page_info = connection.get("pageInfo") or {}
        after = str(page_info.get("endCursor") or "") or None
        terminal = not bool(page_info.get("hasNextPage"))
        yield PollPage(tuple(documents), next_cursor=newest if terminal else request.cursor, next_checkpoint=None if terminal else after, snapshot_complete=terminal)
        if terminal:
            return
    yield PollPage(next_cursor=request.cursor, next_checkpoint=after, snapshot_complete=False, provider_metadata={"reason": "page_limit"})
