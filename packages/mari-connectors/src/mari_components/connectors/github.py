"""GitHub repository, issue/PR, commit, and deletion ingestion."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import fnmatch
import json
from typing import Any, Iterator, Mapping
import urllib.parse

from mari_components.connectors._shared import json_response
from mari_components.connectors.protocol import ValidationResult
from mari_components.errors import AuthenticationFailure, PermanentFailure
from mari_components.http import HttpRequest, HttpTransport
from mari_components.types import DocumentACL, KnowledgeDocument, PollPage, PollRequest, Tombstone


API = "https://api.github.com"
DEFAULT_KNOWLEDGE_PATHS = (
    "*.md", "*.mdx", "*.rst", "*.adoc", "*.asciidoc", "*.txt", "README", "README.*",
)
GITHUB_CONTENT_TYPES = frozenset({"files", "issues", "pull_requests", "commits"})


@dataclass(frozen=True, slots=True)
class GitHubConfig:
    token: str
    repository: str
    branch: str = ""
    paths: tuple[str, ...] = DEFAULT_KNOWLEDGE_PATHS
    content_types: tuple[str, ...] = ("files",)

    def __post_init__(self) -> None:
        parts = self.repository.strip().split("/")
        if not self.token.strip() or len(parts) != 2 or not all(parts):
            raise ValueError("GitHub token and owner/repository are required")
        unknown = set(self.content_types) - GITHUB_CONTENT_TYPES
        if unknown:
            raise ValueError(f"Unknown GitHub content types: {', '.join(sorted(unknown))}")


@dataclass(frozen=True, slots=True)
class GitHubCursor:
    head: str = ""
    item_since: str = ""
    files: Mapping[str, str] | None = None

    def encode(self) -> str:
        return json.dumps(
            {"head": self.head, "item_since": self.item_since, "files": dict(self.files or {})},
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def decode(cls, value: str | None) -> "GitHubCursor":
        if not value:
            return cls(files={})
        try:
            data = json.loads(value)
            files = data.get("files") or {}
            if not isinstance(data, dict) or not isinstance(files, dict):
                raise TypeError
            return cls(str(data.get("head") or ""), str(data.get("item_since") or ""), {
                str(key): str(item) for key, item in files.items()
            })
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("invalid GitHub cursor") from error


def _headers(config: GitHubConfig) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.token.strip()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "mari-components",
    }


def _get(config: GitHubConfig, path: str, params: Mapping[str, Any] | None, *, http: HttpTransport) -> Any:
    query = "?" + urllib.parse.urlencode(params) if params else ""
    return json_response(http, HttpRequest("GET", API + path + query, _headers(config)))


def validate_github(config: GitHubConfig, *, http: HttpTransport) -> ValidationResult:
    try:
        repo = _get(config, f"/repos/{config.repository}", None, http=http)
    except Exception as error:
        return ValidationResult(False, str(error))
    if not isinstance(repo, dict) or not repo.get("full_name"):
        return ValidationResult(False, "GitHub repository response is invalid")
    return ValidationResult(True, identity=str(repo["full_name"]))


def list_github_repositories(token: str, *, http: HttpTransport, page_limit: int = 10) -> tuple[dict, ...]:
    config = GitHubConfig(token, "placeholder/repository")
    rows: list[dict] = []
    for page in range(1, max(1, page_limit) + 1):
        value = _get(
            config,
            "/user/repos",
            {"sort": "updated", "direction": "desc", "per_page": 100, "page": page},
            http=http,
        )
        if not isinstance(value, list):
            raise PermanentFailure("GitHub repositories response is invalid")
        rows.extend(item for item in value if isinstance(item, dict))
        if len(value) < 100:
            break
    return tuple(rows)


def _paginate(
    config: GitHubConfig,
    path: str,
    params: Mapping[str, Any],
    *,
    http: HttpTransport,
    page_limit: int,
) -> tuple[list[dict], bool]:
    rows: list[dict] = []
    for page in range(1, page_limit + 1):
        value = _get(config, path, {**params, "per_page": 100, "page": page}, http=http)
        if not isinstance(value, list):
            raise PermanentFailure(f"GitHub returned invalid pagination data for {path}")
        rows.extend(item for item in value if isinstance(item, dict))
        if len(value) < 100:
            return rows, True
    return rows, False


def _tree(
    config: GitHubConfig, ref: str, *, http: HttpTransport, request_limit: int
) -> tuple[list[dict], bool]:
    encoded = urllib.parse.quote(ref, safe="")
    value = _get(config, f"/repos/{config.repository}/git/trees/{encoded}", {"recursive": "1"}, http=http)
    if not isinstance(value, dict):
        raise PermanentFailure("GitHub tree response is invalid")
    if not value.get("truncated"):
        return [item for item in value.get("tree") or [] if item.get("type") == "blob"], True
    blobs: list[dict] = []
    stack = [(ref, "")]
    requests = 0
    while stack and requests < request_limit:
        sha, prefix = stack.pop()
        page = _get(
            config,
            f"/repos/{config.repository}/git/trees/{urllib.parse.quote(sha, safe='')}",
            None,
            http=http,
        )
        requests += 1
        if page.get("truncated"):
            return blobs, False
        for item in page.get("tree") or []:
            path = f"{prefix}/{item.get('path', '')}".strip("/")
            normalized = {**item, "path": path}
            if item.get("type") == "blob":
                blobs.append(normalized)
            elif item.get("type") == "tree" and item.get("sha"):
                stack.append((str(item["sha"]), path))
    return blobs, not stack


def _blob(config: GitHubConfig, sha: str, *, http: HttpTransport) -> str:
    value = _get(
        config,
        f"/repos/{config.repository}/git/blobs/{urllib.parse.quote(sha, safe='')}",
        None,
        http=http,
    )
    try:
        raw = base64.b64decode(str(value.get("content") or ""))
        return raw.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return ""


def github_repository(config: GitHubConfig, *, http: HttpTransport) -> dict:
    value = _get(config, f"/repos/{config.repository}", None, http=http)
    if not isinstance(value, dict):
        raise PermanentFailure("GitHub repository response is invalid")
    return value


def validate_github_team(token: str, organization: str, team: str, *,
                         http: HttpTransport) -> ValidationResult:
    """Validate a team slug without introducing product membership semantics."""
    config = GitHubConfig(token, "placeholder/repository")
    try:
        value = _get(
            config,
            f"/orgs/{urllib.parse.quote(organization, safe='')}/teams/"
            f"{urllib.parse.quote(team, safe='')}",
            None,
            http=http,
        )
    except Exception as error:
        return ValidationResult(False, str(error))
    if not isinstance(value, dict) or not value.get("slug"):
        return ValidationResult(False, "GitHub team response is invalid")
    return ValidationResult(True, identity=f"{organization}/{value['slug']}")


def github_head(config: GitHubConfig, branch: str, *, http: HttpTransport) -> str:
    value = _get(
        config,
        f"/repos/{config.repository}/commits/{urllib.parse.quote(branch, safe='')}",
        None,
        http=http,
    )
    sha = str(value.get("sha") or "")
    if not sha:
        raise PermanentFailure("GitHub branch has no head commit")
    return sha


def github_tree(config: GitHubConfig, ref: str, *, http: HttpTransport, request_limit: int = 2000) -> tuple[tuple[dict, ...], bool]:
    rows, complete = _tree(config, ref, http=http, request_limit=request_limit)
    return tuple(rows), complete


def github_blob(config: GitHubConfig, sha: str, *, http: HttpTransport) -> str:
    return _blob(config, sha, http=http)


def github_issues(config: GitHubConfig, since: str = "", *, http: HttpTransport, page_limit: int = 50) -> tuple[tuple[dict, ...], bool]:
    params: dict[str, Any] = {"state": "all", "sort": "updated", "direction": "asc"}
    if since:
        params["since"] = since
    rows, complete = _paginate(config, f"/repos/{config.repository}/issues", params, http=http, page_limit=page_limit)
    return tuple(rows), complete


def github_issue_comments(config: GitHubConfig, number: int, *, http: HttpTransport, limit: int = 30) -> tuple[dict, ...]:
    rows, _complete = _paginate(
        config,
        f"/repos/{config.repository}/issues/{int(number)}/comments",
        {},
        http=http,
        page_limit=max(1, (limit + 99) // 100),
    )
    return tuple(rows[-limit:])


def github_pull_request(config: GitHubConfig, number: int, *, http: HttpTransport) -> dict:
    """Fetch the canonical pull-request body for an interactive destination."""
    value = _get(config, f"/repos/{config.repository}/pulls/{int(number)}", None, http=http)
    if not isinstance(value, dict) or not value.get("number"):
        raise PermanentFailure("GitHub pull request response is invalid")
    return value


def github_pull_files(config: GitHubConfig, number: int, *, http: HttpTransport,
                      page_limit: int = 10) -> tuple[dict, ...]:
    """Fetch changed-file patches with the connector's normal bounded paging."""
    rows, complete = _paginate(
        config, f"/repos/{config.repository}/pulls/{int(number)}/files", {},
        http=http, page_limit=page_limit,
    )
    if not complete:
        raise PermanentFailure("GitHub pull request files exceeded the configured page limit")
    return tuple(rows)


def github_commits(config: GitHubConfig, branch: str, since: str = "", *, http: HttpTransport, page_limit: int = 50) -> tuple[tuple[dict, ...], bool]:
    params: dict[str, Any] = {"sha": branch}
    if since:
        params["since"] = since
    rows, complete = _paginate(config, f"/repos/{config.repository}/commits", params, http=http, page_limit=page_limit)
    return tuple(rows), complete


def _issue_document(
    config: GitHubConfig, issue: Mapping[str, Any], *, http: HttpTransport, page_limit: int
) -> tuple[KnowledgeDocument, bool]:
    number = int(issue["number"])
    comments: list[dict] = []
    complete = True
    if int(issue.get("comments") or 0):
        comments, complete = _paginate(
            config,
            f"/repos/{config.repository}/issues/{number}/comments",
            {},
            http=http,
            page_limit=page_limit,
        )
    kind = "pull request" if issue.get("pull_request") else "issue"
    body = [str(issue.get("body") or "")]
    for comment in comments:
        author = str((comment.get("user") or {}).get("login") or "unknown")
        body.append(f"\n\nComment by @{author}:\n{comment.get('body') or ''}")
    return KnowledgeDocument(
        f"{kind.replace(' ', '_')}:{number}",
        f"{kind.title()} #{number}: {issue.get('title') or ''}",
        "".join(body).strip(),
        revision=str(issue.get("updated_at") or ""),
        updated_at=str(issue.get("updated_at") or ""),
        source_url=str(issue.get("html_url") or ""),
        acl=DocumentACL("connector_scope"),
        metadata={"kind": kind, "number": number, "state": str(issue.get("state") or "")},
    ), complete


def poll_github(
    config: GitHubConfig, request: PollRequest, *, http: HttpTransport
) -> Iterator[PollPage]:
    previous = GitHubCursor.decode(request.cursor)
    repository = _get(config, f"/repos/{config.repository}", None, http=http)
    branch = config.branch.strip() or str(repository.get("default_branch") or "main")
    commit = _get(
        config,
        f"/repos/{config.repository}/commits/{urllib.parse.quote(branch, safe='')}",
        None,
        http=http,
    )
    head = str(commit.get("sha") or "")
    if not head:
        raise PermanentFailure("GitHub branch has no head commit")
    head_detail = commit.get("commit") or {}
    head_updated_at = str(
        (head_detail.get("committer") or {}).get("date")
        or (head_detail.get("author") or {}).get("date")
        or ""
    )
    if not head_updated_at:
        raise PermanentFailure("GitHub head commit has no timestamp")
    tree, tree_complete = ([], True)
    if "files" in config.content_types:
        tree, tree_complete = _tree(
            config, head, http=http, request_limit=max(1, request.page_limit * request.page_size)
        )
    files = {
        str(item.get("path") or ""): str(item.get("sha") or "")
        for item in tree
        if item.get("path") and (
            not config.paths
            or any(fnmatch.fnmatch(str(item["path"]), pattern) for pattern in config.paths)
        )
    }
    documents: list[KnowledgeDocument] = []
    for path, sha in sorted(files.items()):
        if previous.files and previous.files.get(path) == sha:
            continue
        body = _blob(config, sha, http=http)
        if not body:
            continue
        documents.append(
            KnowledgeDocument(
                f"file:{path}",
                path,
                body,
                revision=sha,
                updated_at=head_updated_at,
                source_url=f"https://github.com/{config.repository}/blob/{branch}/{urllib.parse.quote(path)}",
                acl=DocumentACL("connector_scope"),
                metadata={"kind": "file", "path": path, "branch": branch},
            )
        )
    tombstones = tuple(
        Tombstone(f"file:{path}") for path in sorted(set(previous.files or {}) - set(files))
    )

    item_params: dict[str, Any] = {"state": "all", "sort": "updated", "direction": "asc"}
    if previous.item_since:
        item_params["since"] = previous.item_since
    include_issues = "issues" in config.content_types
    include_pull_requests = "pull_requests" in config.content_types
    issues, issues_complete = ([], True)
    if include_issues or include_pull_requests:
        issues, issues_complete = _paginate(
            config,
            f"/repos/{config.repository}/issues",
            item_params,
            http=http,
            page_limit=request.page_limit,
        )
    item_complete = issues_complete
    newest = previous.item_since
    for issue in issues:
        is_pull_request = bool(issue.get("pull_request"))
        if (is_pull_request and not include_pull_requests) or (not is_pull_request and not include_issues):
            continue
        document, comments_complete = _issue_document(
            config, issue, http=http, page_limit=request.page_limit
        )
        documents.append(document)
        item_complete = item_complete and comments_complete
        newest = max(newest, document.updated_at)

    commit_params: dict[str, Any] = {"sha": branch}
    if previous.item_since:
        commit_params["since"] = previous.item_since
    commits, commits_complete = ([], True)
    if "commits" in config.content_types:
        commits, commits_complete = _paginate(
            config,
            f"/repos/{config.repository}/commits",
            commit_params,
            http=http,
            page_limit=request.page_limit,
        )
    for item in commits:
        detail = item.get("commit") or {}
        author = detail.get("author") or {}
        updated = str(author.get("date") or "")
        sha = str(item.get("sha") or "")
        documents.append(
            KnowledgeDocument(
                f"commit:{sha}",
                f"Commit {sha[:8]}: {str(detail.get('message') or '').splitlines()[0]}",
                str(detail.get("message") or ""),
                revision=sha,
                updated_at=updated,
                source_url=str(item.get("html_url") or ""),
                acl=DocumentACL("connector_scope"),
                metadata={"kind": "commit", "sha": sha},
            )
        )
        newest = max(newest, updated)
    complete = tree_complete and item_complete and commits_complete
    cursor = GitHubCursor(head, newest, files).encode() if complete else request.cursor
    yield PollPage(
        tuple(documents),
        tombstones,
        next_cursor=cursor,
        snapshot_complete=complete,
        provider_metadata={
            "tree_complete": tree_complete,
            "issues_complete": item_complete,
            "commits_complete": commits_complete,
        },
    )
