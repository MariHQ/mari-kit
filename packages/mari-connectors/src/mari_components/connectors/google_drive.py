"""Google Drive/Docs validation, OAuth refresh, snapshots, and Changes polling."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterator, Mapping
import urllib.parse

from mari_components.connectors._shared import json_response, send
from mari_components.connectors.protocol import ValidationResult
from mari_components.errors import AuthenticationFailure, IncompleteSnapshot, PermanentFailure
from mari_components.http import HttpRequest, HttpTransport
from mari_components.types import (
    DocumentACL,
    KnowledgeDocument,
    PollPage,
    PollRequest,
    Principal,
    Tombstone,
)


API = "https://www.googleapis.com/drive/v3"
TOKEN_API = "https://oauth2.googleapis.com/token"
DOC_MIME = "application/vnd.google-apps.document"
TEXT_MIMES = ("text/plain", "text/markdown")


@dataclass(frozen=True, slots=True)
class GoogleDriveConfig:
    access_token: str
    folder_id: str = ""


@dataclass(frozen=True, slots=True)
class GoogleOAuthRefresh:
    refresh_token: str
    client_id: str
    client_secret: str


@dataclass(frozen=True, slots=True)
class GoogleDriveWatch:
    channel_id: str
    resource_id: str
    expiration_ms: int | None = None


def start_google_drive_watch(
    config: GoogleDriveConfig,
    page_token: str,
    callback_url: str,
    channel_id: str,
    channel_token: str,
    *,
    http: HttpTransport,
    expiration_ms: int | None = None,
) -> GoogleDriveWatch:
    """Register a Drive Changes push channel through an injected transport."""
    if not page_token.strip():
        raise ValueError("Google Drive Changes page token is required")
    if not callback_url.startswith("https://"):
        raise ValueError("Google Drive watch callback must use HTTPS")
    if not channel_id.strip() or not channel_token.strip():
        raise ValueError("Google Drive watch channel id and token are required")
    body: dict[str, Any] = {
        "id": channel_id.strip(),
        "type": "web_hook",
        "address": callback_url,
        "token": channel_token,
    }
    if expiration_ms is not None:
        body["expiration"] = str(expiration_ms)
    query = urllib.parse.urlencode(
        {"pageToken": page_token.strip(), "supportsAllDrives": "true"}
    )
    value = json_response(
        http,
        HttpRequest(
            "POST",
            f"{API}/changes/watch?{query}",
            {
                "Authorization": f"Bearer {config.access_token.strip()}",
                "Content-Type": "application/json",
            },
            json.dumps(body, separators=(",", ":")).encode(),
        ),
    )
    if not isinstance(value, dict) or not str(value.get("resourceId") or ""):
        raise PermanentFailure("Google Drive watch returned no resource id")
    raw_expiration = value.get("expiration")
    try:
        provider_expiration = int(raw_expiration) if raw_expiration is not None else None
    except (TypeError, ValueError):
        provider_expiration = None
    return GoogleDriveWatch(
        channel_id=str(value.get("id") or channel_id),
        resource_id=str(value["resourceId"]),
        expiration_ms=provider_expiration,
    )


def refresh_google_access_token(credentials: GoogleOAuthRefresh, *, http: HttpTransport) -> str:
    if not credentials.refresh_token or not credentials.client_id or not credentials.client_secret:
        raise ValueError("complete Google OAuth refresh credentials are required")
    body = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": credentials.refresh_token,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
        }
    ).encode()
    value = json_response(
        http,
        HttpRequest("POST", TOKEN_API, {"Content-Type": "application/x-www-form-urlencoded"}, body),
    )
    token = str(value.get("access_token") or "") if isinstance(value, dict) else ""
    if not token:
        raise AuthenticationFailure("Google OAuth refresh returned no access token")
    return token


def _get(config: GoogleDriveConfig, path: str, *, http: HttpTransport) -> Any:
    if not config.access_token.strip():
        raise AuthenticationFailure("Google Drive access token is required")
    return json_response(
        http,
        HttpRequest("GET", API + path, {"Authorization": f"Bearer {config.access_token.strip()}"}),
    )


def validate_google_drive(config: GoogleDriveConfig, *, http: HttpTransport) -> ValidationResult:
    try:
        value = _get(config, "/about?fields=user", http=http)
    except Exception as error:
        return ValidationResult(False, str(error))
    user = value.get("user") if isinstance(value, dict) else None
    identity = str((user or {}).get("emailAddress") or (user or {}).get("displayName") or "")
    return ValidationResult(True, identity=identity)


def _acl(file: Mapping[str, Any]) -> DocumentACL:
    principals: set[Principal] = set()
    public = False
    for permission in file.get("permissions") or []:
        if not isinstance(permission, dict) or permission.get("deleted"):
            continue
        kind = str(permission.get("type") or "")
        if kind == "anyone":
            public = True
        elif kind in {"user", "group"} and permission.get("emailAddress"):
            principals.add(Principal(kind, str(permission["emailAddress"]).casefold()))
        elif kind == "domain" and permission.get("domain"):
            principals.add(Principal("domain", str(permission["domain"]).casefold()))
    return DocumentACL("public" if public else "restricted", tuple(sorted(principals, key=repr)))


def _file_body(config: GoogleDriveConfig, file: Mapping[str, Any], *, http: HttpTransport) -> str:
    file_id = urllib.parse.quote(str(file["id"]), safe="")
    if file.get("mimeType") == DOC_MIME:
        path = f"/files/{file_id}/export?mimeType=text%2Fplain"
    else:
        path = f"/files/{file_id}?alt=media"
    response = send(
        http,
        HttpRequest("GET", API + path, {"Authorization": f"Bearer {config.access_token.strip()}"}),
    )
    return response.body.decode("utf-8", "replace")


def _document(config: GoogleDriveConfig, file: Mapping[str, Any], *, http: HttpTransport) -> KnowledgeDocument:
    file_id = str(file.get("id") or "")
    return KnowledgeDocument(
        file_id,
        str(file.get("name") or file_id),
        _file_body(config, file, http=http),
        revision=str(file.get("md5Checksum") or file.get("modifiedTime") or ""),
        updated_at=str(file.get("modifiedTime") or ""),
        source_url=f"https://drive.google.com/open?id={urllib.parse.quote(file_id, safe='')}",
        acl=_acl(file),
        metadata={"mime_type": str(file.get("mimeType") or "")},
    )


def _file_fields() -> str:
    return "id,name,mimeType,modifiedTime,md5Checksum,trashed,parents,permissions(type,emailAddress,domain,deleted)"


def _in_scope(config: GoogleDriveConfig, file: Mapping[str, Any]) -> bool:
    return not config.folder_id.strip() or config.folder_id.strip() in (file.get("parents") or [])


def poll_google_drive_changes(
    config: GoogleDriveConfig, request: PollRequest, *, http: HttpTransport
) -> Iterator[PollPage]:
    raw_cursor = str(request.checkpoint or request.cursor or "")
    token = raw_cursor.removeprefix("changes:")
    if not token:
        raise ValueError("Google Drive Changes cursor is required")
    for _ in range(request.page_limit):
        params = {
            "pageToken": token,
            "pageSize": str(request.page_size),
            "includeRemoved": "true",
            "includeItemsFromAllDrives": "true",
            "supportsAllDrives": "true",
            "fields": f"nextPageToken,newStartPageToken,changes(fileId,removed,file({_file_fields()}))",
        }
        try:
            data = _get(config, "/changes?" + urllib.parse.urlencode(params), http=http)
        except PermanentFailure as error:
            if "HTTP 410" in str(error):
                raise IncompleteSnapshot("Google Drive Changes token expired") from error
            raise
        documents: list[KnowledgeDocument] = []
        tombstones: list[Tombstone] = []
        for change in data.get("changes") or []:
            file = change.get("file") or {}
            file_id = str(change.get("fileId") or file.get("id") or "")
            if not file_id:
                continue
            if change.get("removed") or file.get("trashed") or not _in_scope(config, file):
                tombstones.append(Tombstone(file_id))
            elif file.get("mimeType") in (DOC_MIME, *TEXT_MIMES):
                documents.append(_document(config, file, http=http))
        next_page = str(data.get("nextPageToken") or "")
        terminal_cursor = str(data.get("newStartPageToken") or "")
        terminal = not next_page
        if terminal and not terminal_cursor:
            raise PermanentFailure("Google Drive Changes ended without a new start token")
        yield PollPage(
            tuple(documents),
            tuple(tombstones),
            next_cursor=f"changes:{terminal_cursor}" if terminal else request.cursor,
            next_checkpoint=None if terminal else f"changes:{next_page}",
            snapshot_complete=terminal,
        )
        if terminal:
            return
        token = next_page
    yield PollPage(
        next_cursor=request.cursor,
        next_checkpoint=f"changes:{token}",
        snapshot_complete=False,
        provider_metadata={"reason": "page_limit"},
    )


def poll_google_drive(
    config: GoogleDriveConfig, request: PollRequest, *, http: HttpTransport
) -> Iterator[PollPage]:
    if str(request.cursor or "").startswith("changes:") or str(request.checkpoint or "").startswith("changes:"):
        yield from poll_google_drive_changes(config, request, http=http)
        return
    start = ""
    page_token = ""
    if request.checkpoint:
        try:
            saved = json.loads(request.checkpoint)
            start = str(saved["start_token"])
            page_token = str(saved["page_token"])
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError("invalid Google Drive snapshot checkpoint") from error
    if not start:
        token_data = _get(config, "/changes/startPageToken", http=http)
        start = str(token_data.get("startPageToken") or "")
        if not start:
            raise PermanentFailure("Google Drive returned no initial Changes token")
    for _ in range(request.page_limit):
        terms = [
            "trashed = false",
            f"(mimeType = '{DOC_MIME}' or mimeType = '{TEXT_MIMES[0]}' or mimeType = '{TEXT_MIMES[1]}')",
        ]
        if config.folder_id.strip():
            escaped = config.folder_id.replace("\\", "\\\\").replace("'", "\\'")
            terms.append(f"'{escaped}' in parents")
        params = {
            "q": " and ".join(terms),
            "pageSize": str(request.page_size),
            "fields": f"nextPageToken,files({_file_fields()})",
        }
        if page_token:
            params["pageToken"] = page_token
        data = _get(config, "/files?" + urllib.parse.urlencode(params), http=http)
        documents = tuple(_document(config, file, http=http) for file in data.get("files") or [])
        page_token = str(data.get("nextPageToken") or "")
        terminal = not page_token
        yield PollPage(
            documents,
            next_cursor=f"changes:{start}" if terminal else request.cursor,
            next_checkpoint=None if terminal else json.dumps(
                {"start_token": start, "page_token": page_token},
                sort_keys=True,
                separators=(",", ":"),
            ),
            snapshot_complete=terminal,
        )
        if terminal:
            return
    yield PollPage(
        next_cursor=request.cursor,
        next_checkpoint=json.dumps(
            {"start_token": start, "page_token": page_token},
            sort_keys=True,
            separators=(",", ":"),
        ),
        snapshot_complete=False,
        provider_metadata={"reason": "page_limit"},
    )
