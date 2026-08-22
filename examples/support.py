"""Deterministic injected boundaries shared by the examples."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from urllib.parse import parse_qs, urlparse

import numpy as np

from mari_components import KnowledgeDocument
from mari_components.http import HttpRequest, HttpResponse


def required(environment: Mapping[str, str], key: str) -> str:
    value = str(environment.get(key) or "").strip()
    if not value:
        raise RuntimeError(f"{key} is required")
    return value


def selected_mode(environment: Mapping[str, str]) -> str:
    mode = required(environment, "MARI_EXAMPLE_MODE")
    if mode not in {"fake", "live"}:
        raise RuntimeError("MARI_EXAMPLE_MODE must be fake or live")
    return mode


def urllib_transport(request: HttpRequest) -> HttpResponse:
    """Standard-library adapter used by the live example projects."""
    outbound = urllib.request.Request(
        request.url,
        data=request.body,
        headers=dict(request.headers),
        method=request.method,
    )
    try:
        with urllib.request.urlopen(outbound, timeout=request.timeout) as response:
            return HttpResponse(
                response.status, dict(response.headers.items()), response.read()
            )
    except urllib.error.HTTPError as error:
        return HttpResponse(error.code, dict(error.headers.items()), error.read())


def json_generator(
    environment: Mapping[str, str],
    fixture: Callable[[str, str], object],
) -> Callable[[str, str], object]:
    """Select an explicit fixture or DeepSeek JSON-completion boundary."""
    backend = required(environment, "MARI_EXAMPLE_MODEL")
    if backend == "fixture":
        return fixture
    if backend != "deepseek":
        raise RuntimeError("MARI_EXAMPLE_MODEL must be fixture or deepseek")
    from openai import OpenAI

    base_url = str(
        environment.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com"
    ).rstrip("/")
    token = required(environment, "DEEPSEEK_API_KEY")
    model = required(environment, "DEEPSEEK_MODEL")
    client = OpenAI(api_key=token, base_url=base_url)

    def generate(prompt: str, version: str) -> object:
        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            max_tokens=1200,
            messages=[
                {
                    "role": "system",
                    "content": f"Return JSON for recipe {version} exactly.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise RuntimeError("DeepSeek JSON response was truncated")
        content = choice.message.content
        if not content:
            raise RuntimeError("DeepSeek returned empty JSON content")
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise RuntimeError("model returned a non-object JSON value")
        return parsed

    return generate


def _fixture_embedding(text: str, dimensions: int = 64) -> tuple[float, ...]:
    aliases = {
        "customers": "customer",
        "refunds": "refund",
        "refunded": "refund",
        "moneyback": "refund",
        "voice": "style",
        "tone": "style",
    }
    values = np.zeros(dimensions, np.float64)
    for raw in re.findall(r"[a-z0-9]+", text.casefold()):
        token = aliases.get(
            raw, raw[:-1] if raw.endswith("s") and len(raw) > 3 else raw
        )
        digest = hashlib.sha256(token.encode()).digest()
        values[int.from_bytes(digest[:4], "big") % dimensions] += 1.0
    norm = float(np.linalg.norm(values))
    if not norm:
        raise ValueError("embedding input must not be empty")
    return tuple(float(value) for value in values / norm)


def text_embedder(
    environment: Mapping[str, str],
) -> Callable[[tuple[str, ...]], tuple[tuple[float, ...], ...]]:
    """Select deterministic fixtures or the OpenAI embeddings endpoint."""
    backend = required(environment, "MARI_EXAMPLE_EMBEDDINGS")
    if backend == "fixture":
        return lambda texts: tuple(_fixture_embedding(text) for text in texts)
    if backend != "openai":
        raise RuntimeError("MARI_EXAMPLE_EMBEDDINGS must be fixture or openai")
    from openai import OpenAI

    token = required(environment, "OPENAI_API_KEY")
    model = required(environment, "OPENAI_EMBEDDING_MODEL")
    base_url = str(
        environment.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
    ).rstrip("/")
    dimensions_text = str(environment.get("OPENAI_EMBEDDING_DIMENSIONS") or "").strip()
    client = OpenAI(api_key=token, base_url=base_url)

    def embed(texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        if not texts or any(not text.strip() for text in texts):
            raise ValueError("embedding inputs must be non-empty strings")
        options: dict[str, object] = {"model": model, "input": list(texts)}
        if dimensions_text:
            options["dimensions"] = int(dimensions_text)
        response = client.embeddings.create(**options)
        rows = sorted(response.data, key=lambda row: row.index)
        if len(rows) != len(texts):
            raise RuntimeError("OpenAI returned the wrong number of embeddings")
        embeddings = tuple(tuple(float(item) for item in row.embedding) for row in rows)
        if not embeddings or any(len(row) != len(embeddings[0]) for row in embeddings):
            raise RuntimeError("OpenAI returned invalid embedding dimensions")
        return embeddings

    return embed


def json_response(value: object, status: int = 200) -> HttpResponse:
    return HttpResponse(
        status, {"Content-Type": "application/json"}, json.dumps(value).encode()
    )


class FakeGitHub:
    """A provider-boundary fake, not a connector fake.

    The real GitHub connector still constructs HTTP requests, validates auth,
    walks the repository tree, fetches blobs, advances cursors, and emits
    tombstones. Only GitHub's remote HTTP service is replaced.
    """

    def __init__(self) -> None:
        self.head = "head-1"
        self.files = {
            "README.md": (
                "blob-readme-1",
                "Mari is a product knowledge system for engineering teams.",
            ),
            "docs/release.md": (
                "blob-release-1",
                "Release Mari by deploying the tested main branch.",
            ),
            "private/notes.md": (
                "blob-private-1",
                "This path is excluded by connector configuration.",
            ),
        }
        self.requests: list[HttpRequest] = []

    def update(self) -> None:
        self.head = "head-2"
        self.files["README.md"] = (
            "blob-readme-2",
            "Mari is a product knowledge system with grounded answers and citations.",
        )
        self.files.pop("docs/release.md")

    def publish_without_event(self) -> None:
        self.head = "head-3"
        self.files["README.md"] = (
            "blob-readme-3",
            "Mari is a product knowledge system with repaired polling coverage.",
        )
        self.files["docs/operations.md"] = (
            "blob-operations-1",
            "Operate Mari with polling even when a webhook delivery is lost.",
        )

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        parsed = urlparse(request.url)
        path = parsed.path
        auth = request.headers.get("Authorization", "")
        if auth != "Bearer example-token":
            return json_response({"message": "bad credentials"}, 401)
        if path == "/repos/acme/knowledge":
            return json_response(
                {"full_name": "acme/knowledge", "default_branch": "main"}
            )
        if path == "/repos/acme/knowledge/commits/main":
            return json_response(
                {
                    "sha": self.head,
                    "commit": {"committer": {"date": "2026-08-20T12:00:00Z"}},
                }
            )
        if path == f"/repos/acme/knowledge/git/trees/{self.head}":
            return json_response(
                {
                    "truncated": False,
                    "tree": [
                        {"path": name, "type": "blob", "sha": sha}
                        for name, (sha, _body) in self.files.items()
                    ],
                }
            )
        if "/git/blobs/" in path:
            sha = path.rsplit("/", 1)[-1]
            body = next(
                (body for current, body in self.files.values() if current == sha), None
            )
            return json_response(
                {
                    "content": base64.b64encode((body or "").encode()).decode(),
                    "encoding": "base64",
                }
            )
        if path == "/repos/acme/knowledge/issues":
            return json_response([])
        if path == "/repos/acme/knowledge/commits":
            return json_response([])
        return json_response({"message": f"unhandled example route: {path}"}, 404)


class FakeSlack:
    """Provider-boundary Slack fake with mutable canonical thread state."""

    def __init__(self) -> None:
        self.phase = "initial"
        self.messages = [
            {
                "type": "message",
                "ts": "100.000001",
                "user": "U1",
                "text": "How do releases work?",
            },
            {
                "type": "message",
                "ts": "101.000001",
                "thread_ts": "100.000001",
                "user": "U2",
                "text": "Deploy the tested main branch.",
            },
        ]
        self.requests: list[HttpRequest] = []

    def add_reply(self, text: str = "The release runbook confirms this.") -> None:
        self.phase = "changes"
        timestamp = f"{100 + len(self.messages):d}.000001"
        self.messages.append(
            {
                "type": "message",
                "ts": timestamp,
                "thread_ts": "100.000001",
                "user": "U1",
                "text": text,
            }
        )

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        method = urlparse(request.url).path.rsplit("/", 1)[-1]
        params = parse_qs((request.body or b"").decode())
        if request.headers.get("Authorization") != "Bearer xoxb-example":
            return json_response({"ok": False, "error": "invalid_auth"})
        if method == "users.list":
            return json_response(
                {
                    "ok": True,
                    "members": [
                        {"id": "U1", "profile": {"display_name": "Dana"}},
                        {"id": "U2", "profile": {"display_name": "Lee"}},
                    ],
                    "response_metadata": {"next_cursor": ""},
                }
            )
        if method == "auth.test":
            return json_response(
                {"ok": True, "team": "Example", "team_id": "T-EXAMPLE"}
            )
        if method == "conversations.list":
            return json_response(
                {
                    "ok": True,
                    "channels": [
                        {"id": "C-ENG", "name": "engineering", "is_member": True}
                    ],
                    "response_metadata": {"next_cursor": ""},
                }
            )
        if method == "conversations.history":
            oldest = float((params.get("oldest") or ["0"])[0])
            if not oldest:
                root = dict(self.messages[0])
                root["reply_count"] = len(self.messages) - 1
                root["latest_reply"] = self.messages[-1]["ts"]
                rows = [root]
            else:
                rows = [
                    item for item in self.messages[1:] if float(item["ts"]) >= oldest
                ]
            return json_response(
                {
                    "ok": True,
                    "messages": rows,
                    "response_metadata": {"next_cursor": ""},
                }
            )
        if method == "conversations.replies" and params.get("channel") == ["C-ENG"]:
            return json_response(
                {
                    "ok": True,
                    "messages": self.messages,
                    "response_metadata": {"next_cursor": ""},
                }
            )
        return json_response({"ok": False, "error": f"unhandled_{method}"})


class FakeGoogleDrive:
    """Provider-boundary fake for snapshot, watch, and native Changes pages."""

    document_mime = "application/vnd.google-apps.document"

    def __init__(self) -> None:
        self.phase = "snapshot"
        self.requests: list[HttpRequest] = []
        self.files = {
            "doc-1": {
                "id": "doc-1",
                "name": "Retention policy",
                "mimeType": self.document_mime,
                "modifiedTime": "2026-01-01T00:00:00Z",
                "permissions": [{"type": "group", "emailAddress": "eng@example.com"}],
                "body": "Customer data retention is thirty days.",
            },
            "doc-2": {
                "id": "doc-2",
                "name": "Security handbook",
                "mimeType": self.document_mime,
                "modifiedTime": "2026-01-01T00:00:00Z",
                "permissions": [{"type": "group", "emailAddress": "eng@example.com"}],
                "body": "Security incidents use the on-call process.",
            },
            "doc-4": {
                "id": "doc-4",
                "name": "Access guide",
                "mimeType": self.document_mime,
                "modifiedTime": "2026-01-01T00:00:00Z",
                "permissions": [{"type": "group", "emailAddress": "eng@example.com"}],
                "body": "Access requests require manager approval.",
            },
        }

    def publish_changes(self) -> None:
        self.phase = "changes"
        self.files["doc-1"] = {
            **self.files["doc-1"],
            "modifiedTime": "2026-01-02T00:00:00Z",
            "permissions": [{"type": "group", "emailAddress": "product@example.com"}],
            "body": "Customer data retention is ninety days.",
        }
        self.files.pop("doc-2")
        self.files["doc-3"] = {
            "id": "doc-3",
            "name": "Onboarding checklist",
            "mimeType": self.document_mime,
            "modifiedTime": "2026-01-02T00:00:00Z",
            "permissions": [{"type": "domain", "domain": "example.com"}],
            "body": "Onboarding includes product knowledge training.",
        }
        self.files["doc-4"] = {
            **self.files["doc-4"],
            "modifiedTime": "2026-01-02T00:00:00Z",
            "permissions": [{"type": "group", "emailAddress": "product@example.com"}],
        }

    @staticmethod
    def _metadata(file: Mapping[str, object]) -> dict[str, object]:
        return {key: value for key, value in file.items() if key != "body"}

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        parsed = urlparse(request.url)
        path = parsed.path
        query = parse_qs(parsed.query)
        if (
            path != "/token"
            and request.headers.get("Authorization") != "Bearer drive-example"
        ):
            return json_response({"error": "invalid credentials"}, 401)
        if path.endswith("/about"):
            return json_response({"user": {"emailAddress": "owner@example.com"}})
        if path.endswith("/changes/startPageToken"):
            return json_response({"startPageToken": "stream-1"})
        if path.endswith("/files") and "q" in query:
            return json_response(
                {
                    "files": [self._metadata(file) for file in self.files.values()],
                }
            )
        if path.endswith("/changes/watch") and request.method == "POST":
            return json_response(
                {
                    "id": "example-channel",
                    "resourceId": "example-resource",
                    "expiration": "4102444800000",
                }
            )
        if path.endswith("/changes"):
            if self.phase != "changes":
                return json_response({"changes": [], "newStartPageToken": "stream-1"})
            return json_response(
                {
                    "changes": [
                        {
                            "fileId": "doc-1",
                            "file": self._metadata(self.files["doc-1"]),
                        },
                        {"fileId": "doc-2", "removed": True},
                        {
                            "fileId": "doc-3",
                            "file": self._metadata(self.files["doc-3"]),
                        },
                        {
                            "fileId": "doc-4",
                            "file": self._metadata(self.files["doc-4"]),
                        },
                    ],
                    "newStartPageToken": "stream-2",
                }
            )
        match = re.search(r"/files/([^/]+)/export$", path)
        if match:
            file = self.files.get(match.group(1))
            if file is None:
                return HttpResponse(404, {}, b"")
            return HttpResponse(
                200, {"Content-Type": "text/plain"}, str(file["body"]).encode()
            )
        return json_response({"message": f"unhandled example route: {path}"}, 404)


VOCABULARY = (
    "mari",
    "product",
    "knowledge",
    "release",
    "deploy",
    "main",
    "answers",
    "citations",
    "retention",
    "thirty",
    "ninety",
    "security",
    "onboarding",
)


def token_vectors(text: str) -> np.ndarray:
    """Tiny deterministic stand-in for any caller-supplied embedding model."""
    words = re.findall(r"[a-z]+", text.casefold())
    rows: list[np.ndarray] = []
    for word in words:
        if word in VOCABULARY:
            row = np.zeros(len(VOCABULARY), np.float32)
            row[VOCABULARY.index(word)] = 1.0
            rows.append(row)
    if not rows:
        rows.append(np.full(len(VOCABULARY), 1 / len(VOCABULARY), np.float32))
    return np.stack(rows)


def embed_document(document: KnowledgeDocument) -> np.ndarray:
    return token_vectors(f"{document.title} {document.body}")
