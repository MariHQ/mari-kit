"""Bounded RSS and Atom feed ingestion with conditional batch polling."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass

from mari_components.connectors._shared import header, send
from mari_components.connectors.protocol import ValidationResult
from mari_components.http import HttpRequest, HttpTransport
from mari_components.types import KnowledgeDocument, PollPage, PollRequest


@dataclass(frozen=True, slots=True)
class RSSConfig:
    feed_url: str

    def __post_init__(self) -> None:
        if not self.feed_url.startswith(("https://", "http://")):
            raise ValueError("RSS feed URL must use HTTP or HTTPS")


def _local(element: ET.Element, name: str) -> ET.Element | None:
    return next(
        (child for child in element if child.tag.rsplit("}", 1)[-1] == name), None
    )


def _text(element: ET.Element, *names: str) -> str:
    for name in names:
        child = _local(element, name)
        if child is not None:
            return "".join(child.itertext()).strip()
    return ""


def _link(element: ET.Element) -> str:
    child = _local(element, "link")
    if child is None:
        return ""
    return str(child.attrib.get("href") or child.text or "").strip()


def _parse_cursor(value: str | None) -> tuple[str, str]:
    if not value:
        return "", ""
    try:
        raw = json.loads(value)
        return str(raw.get("etag") or ""), str(raw.get("last_modified") or "")
    except (AttributeError, json.JSONDecodeError) as error:
        raise ValueError("invalid RSS cursor") from error


def _fetch(
    config: RSSConfig,
    cursor: str | None,
    *,
    http: HttpTransport,
    maximum_bytes: int,
):
    etag, modified = _parse_cursor(cursor)
    headers = {
        **({"If-None-Match": etag} if etag else {}),
        **({"If-Modified-Since": modified} if modified else {}),
        "Accept": "application/atom+xml, application/rss+xml, application/xml",
        "User-Agent": "mari-components",
    }
    response = send(http, HttpRequest("GET", config.feed_url, headers))
    if response.status == 304:
        return response
    if len(response.body) > maximum_bytes:
        raise ValueError("RSS feed exceeds maximum_bytes")
    if b"<!DOCTYPE" in response.body.upper() or b"<!ENTITY" in response.body.upper():
        raise ValueError("RSS feed must not contain DTD or entity declarations")
    return response


def validate_rss(config: RSSConfig, *, http: HttpTransport) -> ValidationResult:
    try:
        response = _fetch(config, None, http=http, maximum_bytes=2_097_152)
        root = ET.fromstring(response.body)
    except Exception as error:
        return ValidationResult(False, str(error))
    channel = _local(root, "channel")
    title = _text(root, "title") or _text(
        channel if channel is not None else root, "title"
    )
    return ValidationResult(True, identity=title or config.feed_url)


def poll_rss(
    config: RSSConfig,
    request: PollRequest,
    *,
    http: HttpTransport,
    maximum_bytes: int = 2_097_152,
) -> Iterator[PollPage]:
    response = _fetch(
        config,
        request.checkpoint or request.cursor,
        http=http,
        maximum_bytes=maximum_bytes,
    )
    if response.status == 304:
        yield PollPage(next_cursor=request.cursor, snapshot_complete=True)
        return
    try:
        root = ET.fromstring(response.body)
    except ET.ParseError as error:
        raise ValueError("RSS provider returned invalid XML") from error
    selected_channel = _local(root, "channel")
    channel = selected_channel if selected_channel is not None else root
    entries = [
        element
        for element in channel
        if element.tag.rsplit("}", 1)[-1] in {"item", "entry"}
    ]
    if len(entries) > request.page_size:
        raise ValueError("RSS feed exceeds page_size; increase the batch bound")
    documents = []
    for entry in entries:
        title = _text(entry, "title")
        body = _text(entry, "content", "encoded", "summary", "description")
        link = _link(entry)
        identity = _text(entry, "id", "guid") or link
        if not identity:
            identity = hashlib.sha256(f"{title}\0{body}".encode()).hexdigest()
        revision = hashlib.sha256(
            f"{title}\0{body}\0{link}\0{_text(entry, 'updated', 'pubDate')}".encode()
        ).hexdigest()
        documents.append(
            KnowledgeDocument(
                source_id=f"rss:{config.feed_url}",
                external_id=identity,
                title=title or identity,
                body=body,
                revision=revision,
                source_url=link,
                metadata={"published": _text(entry, "published", "pubDate")},
            )
        )
    cursor = json.dumps(
        {
            "etag": header(response.headers, "etag"),
            "last_modified": header(response.headers, "last-modified"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    yield PollPage(
        upserts=tuple(documents),
        next_cursor=cursor,
        snapshot_complete=True,
    )
