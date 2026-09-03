"""GitLab repository batch ingestion and canonical webhook hints."""

from __future__ import annotations

import fnmatch
import json
import urllib.parse
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from mari_components.connectors._shared import json_response, send
from mari_components.connectors.protocol import ValidationResult
from mari_components.errors import PermanentFailure
from mari_components.http import HttpRequest, HttpTransport
from mari_components.types import KnowledgeDocument, PollPage, PollRequest

DEFAULT_PATHS = ("*.md", "*.mdx", "*.rst", "*.adoc", "*.txt", "README*")


@dataclass(frozen=True, slots=True)
class GitLabConfig:
    token: str = field(repr=False)
    project: str
    branch: str = ""
    paths: tuple[str, ...] = DEFAULT_PATHS
    base_url: str = "https://gitlab.com"

    def __post_init__(self) -> None:
        if not self.token.strip() or not self.project.strip():
            raise ValueError("GitLab token and project are required")
        if not self.base_url.startswith(("https://", "http://")):
            raise ValueError("GitLab base URL must use HTTP or HTTPS")


def _headers(config: GitLabConfig) -> dict[str, str]:
    return {"PRIVATE-TOKEN": config.token.strip(), "User-Agent": "mari-components"}


def _url(config: GitLabConfig, path: str) -> str:
    project = urllib.parse.quote(config.project.strip(), safe="")
    return f"{config.base_url.rstrip('/')}/api/v4/projects/{project}{path}"


def _get(
    config: GitLabConfig,
    path: str,
    params: Mapping[str, Any] | None,
    *,
    http: HttpTransport,
):
    query = "?" + urllib.parse.urlencode(params) if params else ""
    return json_response(
        http, HttpRequest("GET", _url(config, path) + query, _headers(config))
    )


def validate_gitlab(config: GitLabConfig, *, http: HttpTransport) -> ValidationResult:
    try:
        value = _get(config, "", None, http=http)
    except Exception as error:
        return ValidationResult(False, str(error))
    return ValidationResult(
        bool(isinstance(value, dict) and value.get("id")),
        ""
        if isinstance(value, dict) and value.get("id")
        else "invalid project response",
        str(value.get("path_with_namespace") or "") if isinstance(value, dict) else "",
    )


def _checkpoint(value: str | None) -> tuple[str, int]:
    if not value:
        return "", 1
    try:
        raw = json.loads(value)
        return str(raw["head"]), int(raw["page"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("invalid GitLab checkpoint") from error


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    name = path.rsplit("/", 1)[-1]
    return any(
        fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(name, pattern)
        for pattern in patterns
    )


def poll_gitlab(
    config: GitLabConfig,
    request: PollRequest,
    *,
    http: HttpTransport,
    maximum_bytes: int = 5_242_880,
) -> Iterator[PollPage]:
    checkpoint_head, page = _checkpoint(request.checkpoint)
    if checkpoint_head:
        head = checkpoint_head
    else:
        project = _get(config, "", None, http=http)
        branch = config.branch or str(project.get("default_branch") or "main")
        branch_data = _get(
            config,
            f"/repository/branches/{urllib.parse.quote(branch, safe='')}",
            None,
            http=http,
        )
        head = str((branch_data.get("commit") or {}).get("id") or "")
        if not head:
            raise PermanentFailure("GitLab branch response has no head commit")
        if request.cursor == head:
            yield PollPage(next_cursor=head, snapshot_complete=True)
            return
    for _ in range(request.page_limit):
        response = send(
            http,
            HttpRequest(
                "GET",
                _url(config, "/repository/tree")
                + "?"
                + urllib.parse.urlencode(
                    {
                        "ref": head,
                        "recursive": "true",
                        "per_page": request.page_size,
                        "page": page,
                    }
                ),
                _headers(config),
            ),
        )
        try:
            rows = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PermanentFailure("GitLab tree response is invalid") from error
        if not isinstance(rows, list):
            raise PermanentFailure("GitLab tree response is invalid")
        documents = []
        for row in rows:
            if not isinstance(row, dict) or row.get("type") != "blob":
                continue
            path = str(row.get("path") or "")
            size = int(row.get("size") or 0)
            if not path or not _matches(path, config.paths) or size > maximum_bytes:
                continue
            encoded = urllib.parse.quote(path, safe="")
            raw = send(
                http,
                HttpRequest(
                    "GET",
                    _url(config, f"/repository/files/{encoded}/raw")
                    + "?"
                    + urllib.parse.urlencode({"ref": head}),
                    _headers(config),
                ),
            ).body
            if len(raw) > maximum_bytes:
                raise PermanentFailure(f"GitLab file {path!r} exceeds maximum_bytes")
            documents.append(
                KnowledgeDocument(
                    source_id=f"gitlab:{config.project}",
                    external_id=f"file:{path}",
                    title=path.rsplit("/", 1)[-1],
                    body=raw.decode("utf-8", "replace"),
                    revision=str(row.get("id") or head),
                    source_url=f"{config.base_url.rstrip('/')}/{config.project}/-/blob/{head}/{path}",
                    metadata={"path": path, "head": head},
                )
            )
        next_page = next(
            (
                value.strip()
                for key, value in response.headers.items()
                if key.casefold() == "x-next-page"
            ),
            "",
        )
        complete = not next_page
        yield PollPage(
            upserts=tuple(documents),
            next_cursor=head if complete else request.cursor,
            next_checkpoint=(
                None
                if complete
                else json.dumps({"head": head, "page": int(next_page)}, sort_keys=True)
            ),
            snapshot_complete=complete,
        )
        if complete:
            return
        page = int(next_page)
    yield PollPage(
        next_cursor=request.cursor,
        next_checkpoint=json.dumps({"head": head, "page": page}, sort_keys=True),
        snapshot_complete=False,
        provider_metadata={"reason": "page_limit"},
    )
