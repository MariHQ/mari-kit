"""Asana project/task ingestion with offset checkpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Mapping
import urllib.parse

from mari_components.connectors._shared import json_response
from mari_components.connectors.protocol import ValidationResult
from mari_components.http import HttpRequest, HttpTransport
from mari_components.types import DocumentACL, KnowledgeDocument, PollPage, PollRequest


API = "https://app.asana.com/api/1.0"


@dataclass(frozen=True, slots=True)
class AsanaConfig:
    token: str
    workspace_gid: str = ""
    project_gid: str = ""


def _get(config: AsanaConfig, path: str, params: Mapping[str, Any] | None, *, http: HttpTransport) -> dict:
    if not config.token.strip():
        raise ValueError("Asana token is required")
    query = "?" + urllib.parse.urlencode(params) if params else ""
    value = json_response(http, HttpRequest("GET", API + path + query, {"Authorization": f"Bearer {config.token.strip()}"}))
    return value if isinstance(value, dict) else {}


def validate_asana(config: AsanaConfig, *, http: HttpTransport) -> ValidationResult:
    try:
        value = _get(config, "/users/me", None, http=http).get("data") or {}
    except Exception as error:
        return ValidationResult(False, str(error))
    return ValidationResult(True, identity=str(value.get("email") or value.get("name") or ""))


def _pages(config: AsanaConfig, path: str, params: dict[str, Any], request: PollRequest, *, http: HttpTransport) -> tuple[list[dict], bool]:
    rows: list[dict] = []
    offset = ""
    for _ in range(request.page_limit):
        value = _get(config, path, {**params, "limit": request.page_size, **({"offset": offset} if offset else {})}, http=http)
        rows.extend(item for item in value.get("data") or [] if isinstance(item, dict))
        offset = str((value.get("next_page") or {}).get("offset") or "")
        if not offset:
            return rows, True
    return rows, False


def poll_asana(config: AsanaConfig, request: PollRequest, *, http: HttpTransport) -> Iterator[PollPage]:
    complete = True
    if config.project_gid:
        projects = [{"gid": config.project_gid, "name": config.project_gid}]
    else:
        path = "/projects"
        params = {"workspace": config.workspace_gid, "archived": "false", "opt_fields": "gid,name"}
        projects, complete = _pages(config, path, params, request, http=http)
    documents: list[KnowledgeDocument] = []
    newest = str(request.cursor or "")
    for project in projects:
        tasks, task_complete = _pages(
            config,
            f"/projects/{urllib.parse.quote(str(project['gid']), safe='')}/tasks",
            {"opt_fields": "gid,name,notes,html_notes,modified_at,completed,due_on,permalink_url,assignee.name"},
            request,
            http=http,
        )
        complete = complete and task_complete
        for task in tasks:
            updated = str(task.get("modified_at") or "")
            newest = max(newest, updated)
            if request.cursor and updated <= request.cursor:
                continue
            task_id = str(task.get("gid") or "")
            documents.append(
                KnowledgeDocument(
                    f"task:{task_id}",
                    str(task.get("name") or task_id),
                    str(task.get("notes") or task.get("html_notes") or ""),
                    revision=updated,
                    updated_at=updated,
                    source_url=str(task.get("permalink_url") or ""),
                    acl=DocumentACL("connector_scope"),
                    metadata={"project": str(project.get("name") or ""), "completed": bool(task.get("completed"))},
                )
            )
    yield PollPage(tuple(documents), next_cursor=newest if complete else request.cursor, snapshot_complete=complete)
