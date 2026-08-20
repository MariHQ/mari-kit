"""Dropbox native delta-cursor ingestion with explicit deleted entries."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterator

from mari_components.connectors._shared import json_response, send
from mari_components.connectors.protocol import ValidationResult
from mari_components.http import HttpRequest, HttpTransport
from mari_components.types import DocumentACL, KnowledgeDocument, PollPage, PollRequest, Tombstone


API = "https://api.dropboxapi.com/2"
CONTENT = "https://content.dropboxapi.com/2"


@dataclass(frozen=True, slots=True)
class DropboxConfig:
    token: str
    path: str = ""


def _headers(config: DropboxConfig) -> dict[str, str]:
    if not config.token.strip():
        raise ValueError("Dropbox token is required")
    return {"Authorization": f"Bearer {config.token.strip()}"}


def _post(config: DropboxConfig, method: str, body: dict[str, Any], *, http: HttpTransport) -> Any:
    return json_response(
        http,
        HttpRequest(
            "POST",
            f"{API}/{method}",
            {**_headers(config), "Content-Type": "application/json"},
            json.dumps(body).encode(),
        ),
    )


def validate_dropbox(config: DropboxConfig, *, http: HttpTransport) -> ValidationResult:
    try:
        value = _post(config, "users/get_current_account", {}, http=http)
    except Exception as error:
        return ValidationResult(False, str(error))
    return ValidationResult(True, identity=str(value.get("email") or value.get("name", {}).get("display_name") or ""))


def _download(config: DropboxConfig, path: str, *, http: HttpTransport) -> str:
    response = send(
        http,
        HttpRequest(
            "POST",
            f"{CONTENT}/files/download",
            {**_headers(config), "Dropbox-API-Arg": json.dumps({"path": path})},
        ),
    )
    return response.body.decode("utf-8", "replace")


def poll_dropbox(config: DropboxConfig, request: PollRequest, *, http: HttpTransport) -> Iterator[PollPage]:
    cursor = str(request.checkpoint or request.cursor or "")
    for _ in range(request.page_limit):
        if cursor:
            value = _post(config, "files/list_folder/continue", {"cursor": cursor}, http=http)
        else:
            value = _post(
                config,
                "files/list_folder",
                {"path": config.path, "recursive": True, "include_deleted": True, "limit": request.page_size},
                http=http,
            )
        documents: list[KnowledgeDocument] = []
        tombstones: list[Tombstone] = []
        for entry in value.get("entries") or []:
            tag = str(entry.get(".tag") or "")
            external_id = str(entry.get("id") or entry.get("path_lower") or "")
            if not external_id:
                continue
            if tag == "deleted":
                tombstones.append(Tombstone(external_id))
            elif tag == "file" and int(entry.get("size") or 0) <= 1_048_576:
                path = str(entry.get("path_lower") or "")
                documents.append(
                    KnowledgeDocument(
                        external_id,
                        str(entry.get("name") or path),
                        _download(config, path, http=http),
                        revision=str(entry.get("content_hash") or entry.get("rev") or ""),
                        updated_at=str(entry.get("server_modified") or ""),
                        source_url=str(entry.get("preview_url") or ""),
                        acl=DocumentACL("connector_scope"),
                        metadata={"path": path},
                    )
                )
        cursor = str(value.get("cursor") or cursor)
        terminal = not bool(value.get("has_more"))
        yield PollPage(
            tuple(documents),
            tuple(tombstones),
            next_cursor=cursor if terminal else request.cursor,
            next_checkpoint=None if terminal else cursor,
            snapshot_complete=terminal,
        )
        if terminal:
            return
    yield PollPage(next_cursor=request.cursor, next_checkpoint=cursor, snapshot_complete=False, provider_metadata={"reason": "page_limit"})
