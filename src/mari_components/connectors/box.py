"""Box folder batch ingestion with marker checkpoints."""

from __future__ import annotations

import urllib.parse
from collections.abc import Iterator
from dataclasses import dataclass, field

from mari_components.connectors._shared import json_response, send
from mari_components.connectors.protocol import ValidationResult
from mari_components.errors import PermanentFailure
from mari_components.http import HttpRequest, HttpTransport
from mari_components.types import KnowledgeDocument, PollPage, PollRequest

API = "https://api.box.com/2.0"


@dataclass(frozen=True, slots=True)
class BoxConfig:
    access_token: str = field(repr=False)
    folder_id: str = "0"

    def __post_init__(self) -> None:
        if not self.access_token.strip() or not self.folder_id.strip():
            raise ValueError("Box access token and folder ID are required")


def _headers(config: BoxConfig) -> dict[str, str]:
    return {"Authorization": f"Bearer {config.access_token.strip()}"}


def validate_box(config: BoxConfig, *, http: HttpTransport) -> ValidationResult:
    try:
        value = json_response(
            http,
            HttpRequest("GET", f"{API}/folders/{config.folder_id}", _headers(config)),
        )
    except Exception as error:
        return ValidationResult(False, str(error))
    return ValidationResult(
        bool(isinstance(value, dict) and value.get("id")),
        ""
        if isinstance(value, dict) and value.get("id")
        else "invalid folder response",
        str(value.get("name") or value.get("id") or "")
        if isinstance(value, dict)
        else "",
    )


def poll_box(
    config: BoxConfig,
    request: PollRequest,
    *,
    http: HttpTransport,
    maximum_bytes: int = 5_242_880,
) -> Iterator[PollPage]:
    marker = str(request.checkpoint or "")
    for _ in range(request.page_limit):
        params = {
            "limit": request.page_size,
            "usemarker": "true",
            "fields": "id,type,name,sha1,size,modified_at,shared_link",
            **({"marker": marker} if marker else {}),
        }
        value = json_response(
            http,
            HttpRequest(
                "GET",
                f"{API}/folders/{urllib.parse.quote(config.folder_id, safe='')}/items?{urllib.parse.urlencode(params)}",
                _headers(config),
            ),
        )
        if not isinstance(value, dict) or not isinstance(value.get("entries"), list):
            raise PermanentFailure("Box folder response is invalid")
        documents = []
        for item in value["entries"]:
            if not isinstance(item, dict) or item.get("type") != "file":
                continue
            item_id = str(item.get("id") or "")
            size = int(item.get("size") or 0)
            if not item_id or size > maximum_bytes:
                continue
            raw = send(
                http,
                HttpRequest("GET", f"{API}/files/{item_id}/content", _headers(config)),
            ).body
            if len(raw) > maximum_bytes:
                raise PermanentFailure(f"Box file {item_id!r} exceeds maximum_bytes")
            documents.append(
                KnowledgeDocument(
                    source_id=f"box:{config.folder_id}",
                    external_id=item_id,
                    title=str(item.get("name") or item_id),
                    body=raw.decode("utf-8", "replace"),
                    revision=str(
                        item.get("sha1") or item.get("modified_at") or item_id
                    ),
                    updated_at=str(item.get("modified_at") or ""),
                    source_url=str((item.get("shared_link") or {}).get("url") or ""),
                    metadata={"folder_id": config.folder_id, "size": size},
                )
            )
        next_marker = str(value.get("next_marker") or "")
        complete = not next_marker
        yield PollPage(
            upserts=tuple(documents),
            next_cursor=request.cursor,
            next_checkpoint=None if complete else next_marker,
            snapshot_complete=complete,
        )
        if complete:
            return
        if next_marker == marker:
            raise PermanentFailure("Box returned a repeated marker")
        marker = next_marker
    yield PollPage(
        next_cursor=request.cursor,
        next_checkpoint=marker,
        snapshot_complete=False,
        provider_metadata={"reason": "page_limit"},
    )
