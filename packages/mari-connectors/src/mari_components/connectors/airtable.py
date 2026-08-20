"""Airtable base/table snapshot ingestion."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterator
import urllib.parse

from mari_components.connectors._shared import json_response
from mari_components.connectors.protocol import ValidationResult
from mari_components.http import HttpRequest, HttpTransport
from mari_components.types import DocumentACL, KnowledgeDocument, PollPage, PollRequest


API = "https://api.airtable.com/v0"


@dataclass(frozen=True, slots=True)
class AirtableConfig:
    token: str
    base_id: str


def _headers(config: AirtableConfig) -> dict[str, str]:
    if not config.token.strip() or not config.base_id.strip():
        raise ValueError("Airtable token and base id are required")
    return {"Authorization": f"Bearer {config.token.strip()}"}


def validate_airtable(config: AirtableConfig, *, http: HttpTransport) -> ValidationResult:
    try:
        value = json_response(
            http,
            HttpRequest("GET", f"{API}/meta/bases/{urllib.parse.quote(config.base_id, safe='')}/tables", _headers(config)),
        )
    except Exception as error:
        return ValidationResult(False, str(error))
    return ValidationResult(bool(isinstance(value, dict) and "tables" in value), identity=config.base_id)


def poll_airtable(config: AirtableConfig, request: PollRequest, *, http: HttpTransport) -> Iterator[PollPage]:
    metadata = json_response(
        http,
        HttpRequest("GET", f"{API}/meta/bases/{urllib.parse.quote(config.base_id, safe='')}/tables", _headers(config)),
    )
    tables = [table for table in metadata.get("tables") or [] if isinstance(table, dict)]
    documents: list[KnowledgeDocument] = []
    complete = True
    for table in tables:
        records: list[dict] = []
        offset = ""
        for _ in range(request.page_limit):
            query = urllib.parse.urlencode({"pageSize": request.page_size, **({"offset": offset} if offset else {})})
            value = json_response(
                http,
                HttpRequest(
                    "GET",
                    f"{API}/{urllib.parse.quote(config.base_id, safe='')}/{urllib.parse.quote(str(table['id']), safe='')}?{query}",
                    _headers(config),
                ),
            )
            records.extend(item for item in value.get("records") or [] if isinstance(item, dict))
            offset = str(value.get("offset") or "")
            if not offset:
                break
        if offset:
            complete = False
        body = "\n".join(
            json.dumps({"id": record.get("id"), **(record.get("fields") or {})}, sort_keys=True, default=str)
            for record in records
        )
        revision = max((str(record.get("createdTime") or "") for record in records), default="")
        documents.append(
            KnowledgeDocument(
                f"table:{table['id']}",
                str(table.get("name") or table["id"]),
                body,
                revision=revision or str(len(records)),
                source_url=f"https://airtable.com/{config.base_id}/{table['id']}",
                acl=DocumentACL("connector_scope"),
                metadata={"records": len(records)},
            )
        )
    yield PollPage(tuple(documents), next_cursor=request.cursor, snapshot_complete=complete)
