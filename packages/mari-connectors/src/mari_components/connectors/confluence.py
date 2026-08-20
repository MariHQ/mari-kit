"""Confluence Cloud validation, canonical page fetch, and ordered polling."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import html
from html.parser import HTMLParser
import json
from typing import Any, Iterator, Mapping
import urllib.parse

from mari_components.connectors._shared import json_response
from mari_components.connectors.protocol import ValidationResult
from mari_components.errors import AuthenticationFailure, PermanentFailure
from mari_components.http import HttpRequest, HttpTransport
from mari_components.types import DocumentACL, KnowledgeDocument, PollPage, PollRequest


@dataclass(frozen=True, slots=True)
class ConfluenceConfig:
    site_url: str
    email: str
    api_token: str
    space_key: str = ""

    def __post_init__(self) -> None:
        if not self.site_url.strip() or not self.email.strip() or not self.api_token.strip():
            raise ValueError("Confluence site URL, email, and API token are required")


class _StorageText(HTMLParser):
    _BLOCK_END = {"p", "div", "ul", "ol", "table", "tr", "blockquote"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.output: list[str] = []
        self.list_depth = 0
        self.code_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.output.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag in {"ul", "ol"}:
            self.list_depth += 1
        elif tag == "li":
            self.output.append("\n" + "  " * max(self.list_depth - 1, 0) + "- ")
        elif tag in {"pre", "code"} and not self.code_depth:
            self.code_depth += 1
            self.output.append("\n```\n" if tag == "pre" else "`")
        elif tag == "br":
            self.output.append("\n")
        elif tag in {"td", "th"}:
            self.output.append(" | ")
        elif tag == "ac:structured-macro" and dict(attrs).get("ac:name") == "code":
            self.code_depth += 1
            self.output.append("\n```\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.output.append("\n")
        elif tag in {"ul", "ol"}:
            self.list_depth = max(0, self.list_depth - 1)
        elif tag in {"pre", "code"} and self.code_depth:
            self.code_depth -= 1
            self.output.append("\n```\n" if tag == "pre" else "`")
        elif tag == "ac:structured-macro" and self.code_depth:
            self.code_depth -= 1
            self.output.append("\n```\n")
        elif tag in self._BLOCK_END:
            self.output.append("\n")

    def handle_data(self, data: str) -> None:
        self.output.append(data)

    def text(self) -> str:
        lines = [line.rstrip() for line in "".join(self.output).split("\n")]
        cleaned: list[str] = []
        blank = False
        for line in lines:
            if not line:
                if blank:
                    continue
                blank = True
            else:
                blank = False
            cleaned.append(line)
        return "\n".join(cleaned).strip()


def storage_to_text(xhtml: str) -> str:
    if not xhtml:
        return ""
    parser = _StorageText()
    try:
        parser.feed(xhtml.replace("<![CDATA[", "").replace("]]>", ""))
        parser.close()
        return parser.text()
    except Exception:
        import re

        return html.unescape(re.sub(r"<[^>]+>", " ", xhtml)).strip()


def _site(config: ConfluenceConfig) -> str:
    site = config.site_url.strip().rstrip("/")
    return site if site.startswith(("http://", "https://")) else f"https://{site}"


def _get(
    config: ConfluenceConfig,
    path: str,
    params: Mapping[str, Any] | None,
    *,
    http: HttpTransport,
) -> dict[str, Any]:
    encoded = base64.b64encode(f"{config.email.strip()}:{config.api_token.strip()}".encode()).decode()
    query = "?" + urllib.parse.urlencode(params) if params else ""
    value = json_response(
        http,
        HttpRequest(
            "GET",
            _site(config) + path + query,
            {"Authorization": f"Basic {encoded}", "Accept": "application/json"},
        ),
    )
    if not isinstance(value, dict):
        raise PermanentFailure("Confluence returned a non-object response")
    return value


def validate_confluence(config: ConfluenceConfig, *, http: HttpTransport) -> ValidationResult:
    try:
        data = _get(config, "/wiki/rest/api/space", {"limit": 1}, http=http)
    except AuthenticationFailure as error:
        return ValidationResult(False, str(error))
    except Exception as error:
        return ValidationResult(False, str(error))
    if "results" not in data:
        return ValidationResult(False, "Confluence space API returned an unexpected response")
    return ValidationResult(True, identity=config.email.strip())


def _document(page: Mapping[str, Any], site: str) -> KnowledgeDocument:
    page_id = str(page.get("id") or "")
    if not page_id:
        raise PermanentFailure("Confluence page is missing an id")
    body = (((page.get("body") or {}).get("storage") or {}).get("value")) or ""
    version = str((page.get("version") or {}).get("number") or "")
    updated = (((page.get("history") or {}).get("lastUpdated") or {}).get("when")) or (
        (page.get("version") or {}).get("when") or ""
    )
    links = page.get("_links") or {}
    webui = str(links.get("webui") or "")
    return KnowledgeDocument(
        page_id,
        str(page.get("title") or f"Page {page_id}"),
        storage_to_text(str(body)),
        revision=version,
        updated_at=str(updated),
        source_url=site + webui if webui.startswith("/") else webui,
        acl=DocumentACL("connector_scope"),
        metadata={"space_key": str((page.get("space") or {}).get("key") or "")},
    )


def fetch_confluence_page(
    config: ConfluenceConfig, page_id: str, *, http: HttpTransport
) -> KnowledgeDocument | None:
    if not page_id.strip():
        raise ValueError("page_id is required")
    try:
        page = _get(
            config,
            f"/wiki/rest/api/content/{urllib.parse.quote(page_id, safe='')}",
            {"expand": "body.storage,version,history.lastUpdated,space"},
            http=http,
        )
    except PermanentFailure as error:
        if "HTTP 404" in str(error):
            return None
        raise
    if str(page.get("type") or "page") != "page":
        return None
    return _document(page, _site(config))


def poll_confluence(
    config: ConfluenceConfig, request: PollRequest, *, http: HttpTransport
) -> Iterator[PollPage]:
    start = 0
    cursor_time, _, cursor_id = str(request.cursor or "").partition("|")
    if request.checkpoint:
        try:
            checkpoint = json.loads(request.checkpoint)
            start = max(0, int(checkpoint.get("start", 0)))
            cursor_time = str(checkpoint.get("cursor_time") or cursor_time)
            cursor_id = str(checkpoint.get("cursor_id") or cursor_id)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError("invalid Confluence checkpoint") from error
    last_key = (cursor_time, cursor_id)
    for page_number in range(request.page_limit):
        params: dict[str, Any] = {
            "type": "page",
            "expand": "body.storage,version,history.lastUpdated,space,_links",
            "limit": request.page_size,
            "start": start,
            "orderby": "history.lastUpdated asc",
        }
        if config.space_key.strip():
            params["spaceKey"] = config.space_key.strip()
        data = _get(config, "/wiki/rest/api/content", params, http=http)
        documents = sorted(
            (_document(page, _site(config)) for page in data.get("results") or []),
            key=lambda document: (document.updated_at, document.external_id),
        )
        emitted: list[KnowledgeDocument] = []
        for document in documents:
            key = (document.updated_at, document.external_id)
            if request.cursor and key <= (cursor_time, cursor_id):
                continue
            emitted.append(document)
            last_key = max(last_key, key)
        size = int(data.get("size", len(documents)) or 0)
        terminal = not documents or size < request.page_size
        start += size
        next_cursor = "|".join(last_key) if terminal and last_key[0] else request.cursor
        checkpoint = None if terminal else json.dumps(
            {"start": start, "cursor_time": last_key[0], "cursor_id": last_key[1]},
            sort_keys=True,
            separators=(",", ":"),
        )
        yield PollPage(
            tuple(emitted),
            next_cursor=next_cursor,
            next_checkpoint=checkpoint,
            snapshot_complete=terminal,
        )
        if terminal:
            return
    yield PollPage(
        next_cursor=request.cursor,
        next_checkpoint=json.dumps(
            {"start": start, "cursor_time": last_key[0], "cursor_id": last_key[1]},
            sort_keys=True,
            separators=(",", ":"),
        ),
        snapshot_complete=False,
        provider_metadata={"reason": "page_limit"},
    )
