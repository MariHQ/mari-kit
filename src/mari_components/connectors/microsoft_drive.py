"""Microsoft Graph delta ingestion for OneDrive and SharePoint document libraries."""

from __future__ import annotations

import urllib.parse
from collections.abc import Iterator
from dataclasses import dataclass, field

from mari_components.connectors._shared import json_response, send
from mari_components.connectors.protocol import ValidationResult
from mari_components.errors import PermanentFailure
from mari_components.http import HttpRequest, HttpTransport
from mari_components.types import (
    KnowledgeDocument,
    PollPage,
    PollRequest,
    Tombstone,
    content_revision,
)

GRAPH = "https://graph.microsoft.com/v1.0"


def _continuation(value: str) -> str:
    if not value.startswith(f"{GRAPH}/"):
        raise ValueError("Microsoft Graph continuation URL is outside the API origin")
    return value


@dataclass(frozen=True, slots=True)
class MicrosoftDriveConfig:
    access_token: str = field(repr=False)
    drive_id: str
    folder_id: str = "root"
    provider: str = "onedrive"

    def __post_init__(self) -> None:
        if not self.access_token.strip() or not self.drive_id.strip():
            raise ValueError("Microsoft access token and drive ID are required")
        if self.provider not in {"onedrive", "sharepoint"}:
            raise ValueError("Microsoft drive provider must be onedrive or sharepoint")


def _headers(config: MicrosoftDriveConfig) -> dict[str, str]:
    return {"Authorization": f"Bearer {config.access_token.strip()}"}


def validate_microsoft_drive(
    config: MicrosoftDriveConfig, *, http: HttpTransport
) -> ValidationResult:
    try:
        value = json_response(
            http,
            HttpRequest(
                "GET",
                f"{GRAPH}/drives/{urllib.parse.quote(config.drive_id, safe='')}",
                _headers(config),
            ),
        )
    except Exception as error:
        return ValidationResult(False, str(error))
    return ValidationResult(
        bool(isinstance(value, dict) and value.get("id")),
        "" if isinstance(value, dict) and value.get("id") else "invalid drive response",
        str(value.get("name") or value.get("id") or "")
        if isinstance(value, dict)
        else "",
    )


def poll_microsoft_drive(
    config: MicrosoftDriveConfig,
    request: PollRequest,
    *,
    http: HttpTransport,
    maximum_bytes: int = 5_242_880,
) -> Iterator[PollPage]:
    if maximum_bytes < 1:
        raise ValueError("maximum_bytes must be positive")
    continuation = request.checkpoint or request.cursor
    if continuation:
        url = _continuation(continuation)
    else:
        folder = urllib.parse.quote(config.folder_id or "root", safe="")
        url = f"{GRAPH}/drives/{urllib.parse.quote(config.drive_id, safe='')}/items/{folder}/delta"
    source_id = f"{config.provider}:{config.drive_id}"
    for _ in range(request.page_limit):
        value = json_response(http, HttpRequest("GET", url, _headers(config)))
        if not isinstance(value, dict) or not isinstance(value.get("value"), list):
            raise PermanentFailure("Microsoft Graph delta response is invalid")
        documents: list[KnowledgeDocument] = []
        tombstones: list[Tombstone] = []
        for item in value["value"]:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            item_id = str(item["id"])
            if "deleted" in item:
                tombstones.append(Tombstone(source_id=source_id, external_id=item_id))
                continue
            if "file" not in item:
                continue
            size = int(item.get("size") or 0)
            if size > maximum_bytes:
                continue
            raw = send(
                http,
                HttpRequest(
                    "GET",
                    f"{GRAPH}/drives/{urllib.parse.quote(config.drive_id, safe='')}/items/{urllib.parse.quote(item_id, safe='')}/content",
                    _headers(config),
                ),
            ).body
            if len(raw) > maximum_bytes:
                raise PermanentFailure(
                    f"Microsoft file {item_id!r} exceeds maximum_bytes"
                )
            parent = item.get("parentReference") or {}
            body = raw.decode("utf-8", "replace")
            provider_revision = str(item.get("eTag") or item.get("cTag") or item_id)
            documents.append(
                KnowledgeDocument(
                    source_id=source_id,
                    external_id=item_id,
                    title=str(item.get("name") or item_id),
                    body=body,
                    revision=content_revision(body),
                    provider_revision=provider_revision,
                    updated_at=str(item.get("lastModifiedDateTime") or ""),
                    source_url=str(item.get("webUrl") or ""),
                    metadata={
                        "drive_id": config.drive_id,
                        "parent_id": str(parent.get("id") or ""),
                        "mime_type": str(
                            (item.get("file") or {}).get("mimeType") or ""
                        ),
                    },
                )
            )
        next_link = str(value.get("@odata.nextLink") or "")
        delta_link = str(value.get("@odata.deltaLink") or "")
        if next_link:
            next_link = _continuation(next_link)
        if delta_link:
            delta_link = _continuation(delta_link)
        complete = bool(delta_link) and not next_link
        yield PollPage(
            upserts=tuple(documents),
            tombstones=tuple(tombstones),
            next_cursor=delta_link if complete else request.cursor,
            next_checkpoint=next_link or (None if complete else url),
            snapshot_complete=complete,
        )
        if complete:
            return
        if not next_link or next_link == url:
            raise PermanentFailure("Microsoft Graph delta page has no new continuation")
        url = next_link
    yield PollPage(
        next_cursor=request.cursor,
        next_checkpoint=url,
        snapshot_complete=False,
        provider_metadata={"reason": "page_limit"},
    )
