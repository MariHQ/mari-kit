"""Declarative connector catalog and raw-configuration adapters.

The catalog is application-neutral: labels describe provider credentials, not
screens or database columns. Applications may render it, filter it, or replace
individual definitions without maintaining parallel config/validate/poll maps.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from mari_components.errors import AuthenticationFailure
from mari_components.http import HttpTransport
from mari_components.types import ChangeHint, PollPage, PollRequest

from .airtable import AirtableConfig, poll_airtable, validate_airtable
from .asana import AsanaConfig, poll_asana, validate_asana
from .box import BoxConfig, poll_box, validate_box
from .confluence import ConfluenceConfig, poll_confluence, validate_confluence
from .dropbox import DropboxConfig, poll_dropbox, validate_dropbox
from .filesystem import (
    DEFAULT_PATTERNS as DEFAULT_FILESYSTEM_PATTERNS,
)
from .filesystem import (
    FilesystemConfig,
    poll_filesystem,
    validate_filesystem,
)
from .github import DEFAULT_KNOWLEDGE_PATHS, GitHubConfig, poll_github, validate_github
from .gitlab import GitLabConfig, poll_gitlab, validate_gitlab
from .google_drive import (
    GoogleDriveConfig,
    GoogleOAuthRefresh,
    poll_google_drive,
    refresh_google_access_token,
    validate_google_drive,
)
from .jira import JiraConfig, poll_jira, validate_jira
from .linear import LinearConfig, poll_linear, validate_linear
from .microsoft_drive import (
    MicrosoftDriveConfig,
    poll_microsoft_drive,
    validate_microsoft_drive,
)
from .notion import NotionConfig, poll_notion, validate_notion
from .protocol import ConnectorMode, StreamEvent, ValidationResult, VerifyStreamEvent
from .rss import RSSConfig, poll_rss, validate_rss
from .slack import SlackConfig, poll_slack, validate_slack
from .streaming import stream_change_hint
from .trello import TrelloConfig, poll_trello, validate_trello
from .zendesk import ZendeskConfig, poll_zendesk, validate_zendesk

ConfigFactory = Callable[[Mapping[str, Any]], Any]
ValidateOperation = Callable[..., ValidationResult]
PollOperation = Callable[..., Iterator[PollPage]]
RefreshOperation = Callable[[Mapping[str, Any], HttpTransport], Any]
StreamOperation = Callable[..., ChangeHint]


@dataclass(frozen=True, slots=True)
class ConnectorField:
    key: str
    label: str
    secret: bool = False
    required: bool = True
    placeholder: str = ""
    help: str = ""


@dataclass(frozen=True, slots=True)
class ConnectorDefinition:
    key: str
    name: str
    description: str
    fields: tuple[ConnectorField, ...]
    documentation_url: str
    config_factory: ConfigFactory
    validate_operation: ValidateOperation
    poll_operation: PollOperation
    qualifier_fields: tuple[str, ...] = ()
    priority: int = 100
    refresh_operation: RefreshOperation | None = None
    stream_operation: StreamOperation | None = None

    @property
    def modes(self) -> frozenset[ConnectorMode]:
        modes = {ConnectorMode.POLL}
        if self.stream_operation is not None:
            modes.add(ConnectorMode.STREAM)
        return frozenset(modes)

    def supports(self, mode: ConnectorMode) -> bool:
        return mode in self.modes

    def stream(
        self,
        event: StreamEvent,
        *,
        verify: VerifyStreamEvent,
        maximum_bytes: int = 1_048_576,
    ) -> ChangeHint:
        if self.stream_operation is None:
            raise ValueError(f"connector {self.key!r} does not support streaming")
        if event.provider != self.key:
            raise ValueError(
                f"stream event provider {event.provider!r} does not match connector {self.key!r}"
            )
        return self.stream_operation(event, verify=verify, maximum_bytes=maximum_bytes)

    def config(self, values: Mapping[str, Any]) -> Any:
        return self.config_factory(values)

    def validate(
        self, values: Mapping[str, Any], *, http: HttpTransport
    ) -> ValidationResult:
        result = self.validate_operation(self.config(values), http=http)
        if result.ok or self.refresh_operation is None or not _has_refresh(values):
            return result
        return self.validate_operation(self.refresh_operation(values, http), http=http)

    def poll(
        self,
        values: Mapping[str, Any],
        request: PollRequest,
        *,
        http: HttpTransport,
    ) -> Iterator[PollPage]:
        try:
            yield from self.poll_operation(self.config(values), request, http=http)
        except AuthenticationFailure:
            if self.refresh_operation is None or not _has_refresh(values):
                raise
            yield from self.poll_operation(
                self.refresh_operation(values, http), request, http=http
            )


def _text(values: Mapping[str, Any], key: str) -> str:
    return str(values.get(key) or "").strip()


def _has_refresh(values: Mapping[str, Any]) -> bool:
    return all(
        _text(values, key) for key in ("refresh_token", "client_id", "client_secret")
    )


def _csv(values: Mapping[str, Any], key: str) -> tuple[str, ...]:
    return tuple(
        part.strip()
        for part in _text(values, key).replace("\n", ",").split(",")
        if part.strip()
    )


def _github_config(values: Mapping[str, Any]) -> GitHubConfig:
    return GitHubConfig(
        _text(values, "token"),
        _text(values, "repo"),
        _text(values, "branch"),
        _csv(values, "paths") or DEFAULT_KNOWLEDGE_PATHS,
        _csv(values, "content_types") or ("files",),
    )


def _refresh_drive(values: Mapping[str, Any], http: HttpTransport) -> GoogleDriveConfig:
    token = refresh_google_access_token(
        GoogleOAuthRefresh(
            _text(values, "refresh_token"),
            _text(values, "client_id"),
            _text(values, "client_secret"),
        ),
        http=http,
    )
    return GoogleDriveConfig(token, _text(values, "folder_id"))


def _field(
    key: str,
    label: str,
    *,
    secret: bool = False,
    required: bool = True,
    placeholder: str = "",
    help: str = "",
) -> ConnectorField:
    return ConnectorField(key, label, secret, required, placeholder, help)


_DEFINITIONS = (
    ConnectorDefinition(
        "github",
        "GitHub",
        "Documentation files from a repository; other content is opt-in.",
        (
            _field(
                "token",
                "Fine-grained personal access token",
                secret=True,
                placeholder="github_pat_…",
            ),
            _field("repo", "Repository", placeholder="owner/repository"),
            _field("branch", "Branch", required=False, placeholder="main"),
            _field(
                "paths",
                "Knowledge file globs",
                required=False,
                placeholder="*.md, *.mdx, *.rst, *.txt",
                help="Defaults to documentation formats at any depth. Use ** to include every file.",
            ),
            _field(
                "content_types",
                "Content types",
                required=False,
                placeholder="files",
                help="Comma-separated: files, issues, pull_requests, commits. Defaults to files only.",
            ),
        ),
        "https://github.com/settings/personal-access-tokens/new",
        _github_config,
        validate_github,
        poll_github,
        ("repo",),
        10,
        stream_operation=stream_change_hint,
    ),
    ConnectorDefinition(
        "slack",
        "Slack",
        "Threaded channel history visible to the installed application.",
        (
            _field("bot_token", "Bot token", secret=True, placeholder="xoxb-…"),
            _field(
                "history_token",
                "User history token",
                secret=True,
                required=False,
                placeholder="xoxp-…",
            ),
            _field(
                "channels",
                "Channels",
                required=False,
                placeholder="general, engineering",
            ),
        ),
        "https://api.slack.com/tutorials/tracks/getting-a-token",
        lambda v: SlackConfig(
            _text(v, "bot_token"),
            tuple(
                item.strip() for item in _text(v, "channels").split(",") if item.strip()
            ),
            _text(v, "history_token"),
        ),
        validate_slack,
        poll_slack,
        ("channels",),
        20,
        stream_operation=stream_change_hint,
    ),
    ConnectorDefinition(
        "gdrive",
        "Google Drive",
        "Google Docs and text files, including native change tracking.",
        (
            _field(
                "access_token", "OAuth access token", secret=True, placeholder="ya29.…"
            ),
            _field(
                "refresh_token",
                "OAuth refresh token",
                secret=True,
                required=False,
                placeholder="1//…",
            ),
            _field("client_id", "OAuth client ID", required=False),
            _field("client_secret", "OAuth client secret", secret=True, required=False),
            _field("folder_id", "Folder ID", required=False),
        ),
        "https://developers.google.com/drive/api/guides/about-sdk",
        lambda v: GoogleDriveConfig(_text(v, "access_token"), _text(v, "folder_id")),
        validate_google_drive,
        poll_google_drive,
        ("folder_id",),
        30,
        _refresh_drive,
        stream_change_hint,
    ),
    ConnectorDefinition(
        "confluence",
        "Confluence",
        "Pages from readable Confluence spaces.",
        (
            _field("site_url", "Site URL", placeholder="https://company.atlassian.net"),
            _field("email", "Atlassian account email"),
            _field("api_token", "API token", secret=True, placeholder="ATATT…"),
            _field("space_key", "Space key", required=False, placeholder="ENG"),
            _field(
                "webhook_secret", "Webhook signing secret", secret=True, required=False
            ),
        ),
        "https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/",
        lambda v: ConfluenceConfig(
            _text(v, "site_url"),
            _text(v, "email"),
            _text(v, "api_token"),
            _text(v, "space_key"),
        ),
        validate_confluence,
        poll_confluence,
        ("site_url", "space_key"),
        40,
        stream_operation=stream_change_hint,
    ),
    ConnectorDefinition(
        "gitlab",
        "GitLab",
        "Documentation files from a GitLab project repository.",
        (
            _field("token", "Project or personal access token", secret=True),
            _field("project", "Project", placeholder="group/project"),
            _field("branch", "Branch", required=False, placeholder="main"),
            _field(
                "paths",
                "Knowledge file globs",
                required=False,
                placeholder="*.md, *.rst, *.txt",
            ),
            _field(
                "base_url",
                "GitLab URL",
                required=False,
                placeholder="https://gitlab.com",
            ),
        ),
        "https://docs.gitlab.com/api/",
        lambda v: GitLabConfig(
            _text(v, "token"),
            _text(v, "project"),
            _text(v, "branch"),
            _csv(v, "paths") or DEFAULT_KNOWLEDGE_PATHS,
            _text(v, "base_url") or "https://gitlab.com",
        ),
        validate_gitlab,
        poll_gitlab,
        ("project",),
        45,
        stream_operation=stream_change_hint,
    ),
    ConnectorDefinition(
        "onedrive",
        "OneDrive",
        "Files from a Microsoft Graph drive using native delta links.",
        (
            _field("access_token", "OAuth access token", secret=True),
            _field("drive_id", "Drive ID"),
            _field("folder_id", "Folder ID", required=False, placeholder="root"),
        ),
        "https://learn.microsoft.com/graph/api/driveitem-delta",
        lambda v: MicrosoftDriveConfig(
            _text(v, "access_token"),
            _text(v, "drive_id"),
            _text(v, "folder_id") or "root",
            "onedrive",
        ),
        validate_microsoft_drive,
        poll_microsoft_drive,
        ("drive_id", "folder_id"),
        46,
        stream_operation=stream_change_hint,
    ),
    ConnectorDefinition(
        "sharepoint",
        "SharePoint",
        "Files from a SharePoint document library using Microsoft Graph deltas.",
        (
            _field("access_token", "OAuth access token", secret=True),
            _field("drive_id", "Document library drive ID"),
            _field("folder_id", "Folder ID", required=False, placeholder="root"),
        ),
        "https://learn.microsoft.com/graph/api/driveitem-delta",
        lambda v: MicrosoftDriveConfig(
            _text(v, "access_token"),
            _text(v, "drive_id"),
            _text(v, "folder_id") or "root",
            "sharepoint",
        ),
        validate_microsoft_drive,
        poll_microsoft_drive,
        ("drive_id", "folder_id"),
        47,
        stream_operation=stream_change_hint,
    ),
    ConnectorDefinition(
        "box",
        "Box",
        "Files from a Box folder using marker pagination.",
        (
            _field("access_token", "OAuth access token", secret=True),
            _field("folder_id", "Folder ID", required=False, placeholder="0"),
        ),
        "https://developer.box.com/reference/",
        lambda v: BoxConfig(_text(v, "access_token"), _text(v, "folder_id") or "0"),
        validate_box,
        poll_box,
        ("folder_id",),
        48,
        stream_operation=stream_change_hint,
    ),
    ConnectorDefinition(
        "rss",
        "RSS / Atom",
        "Entries from a bounded RSS or Atom feed using conditional requests.",
        (_field("feed_url", "Feed URL", placeholder="https://example.com/feed.xml"),),
        "https://www.rssboard.org/rss-specification",
        lambda v: RSSConfig(_text(v, "feed_url")),
        validate_rss,
        poll_rss,
        ("feed_url",),
        49,
    ),
    ConnectorDefinition(
        "filesystem",
        "Local filesystem",
        "Text and documentation files below an explicit local root.",
        (
            _field("root", "Root directory"),
            _field(
                "patterns",
                "File globs",
                required=False,
                placeholder="*.md, *.rst, *.txt",
            ),
            _field("source_name", "Source name", required=False, placeholder="local"),
        ),
        "https://docs.python.org/3/library/pathlib.html",
        lambda v: FilesystemConfig(
            Path(_text(v, "root")),
            _csv(v, "patterns") or DEFAULT_FILESYSTEM_PATTERNS,
            True,
            _text(v, "source_name") or "local",
        ),
        validate_filesystem,
        poll_filesystem,
        ("root",),
        50,
    ),
    ConnectorDefinition(
        "notion",
        "Notion",
        "Pages shared with a Notion integration.",
        (
            _field(
                "token", "Internal integration token", secret=True, placeholder="ntn_…"
            ),
        ),
        "https://developers.notion.com/docs/create-a-notion-integration",
        lambda v: NotionConfig(_text(v, "token")),
        validate_notion,
        poll_notion,
        priority=50,
    ),
    ConnectorDefinition(
        "jira",
        "Jira",
        "Issues and discussions selected by a JQL query.",
        (
            _field("site_url", "Site URL", placeholder="https://company.atlassian.net"),
            _field("email", "Atlassian account email"),
            _field("api_token", "API token", secret=True, placeholder="ATATT…"),
            _field("project_key", "Project key", required=False),
            _field("jql", "JQL filter", required=False),
        ),
        "https://developer.atlassian.com/cloud/jira/platform/rest/v3/",
        lambda v: JiraConfig(
            _text(v, "site_url"),
            _text(v, "email"),
            _text(v, "api_token"),
            _text(v, "project_key"),
            _text(v, "jql"),
        ),
        validate_jira,
        poll_jira,
        ("site_url", "project_key"),
        60,
    ),
    ConnectorDefinition(
        "airtable",
        "Airtable",
        "Tables and records from an Airtable base.",
        (
            _field("pat", "Personal access token", secret=True, placeholder="pat…"),
            _field("base_id", "Base ID", placeholder="appXXXXXXXXXXXXXX"),
        ),
        "https://airtable.com/developers/web/api/introduction",
        lambda v: AirtableConfig(_text(v, "pat"), _text(v, "base_id")),
        validate_airtable,
        poll_airtable,
        ("base_id",),
    ),
    ConnectorDefinition(
        "asana",
        "Asana",
        "Projects and tasks from an Asana workspace.",
        (
            _field("pat", "Personal access token", secret=True),
            _field("workspace", "Workspace GID", required=False),
            _field("project_gid", "Project GID", required=False),
        ),
        "https://developers.asana.com/docs/personal-access-token",
        lambda v: AsanaConfig(
            _text(v, "pat"), _text(v, "workspace"), _text(v, "project_gid")
        ),
        validate_asana,
        poll_asana,
        ("workspace", "project_gid"),
    ),
    ConnectorDefinition(
        "dropbox",
        "Dropbox",
        "Text and Markdown documents from a Dropbox folder.",
        (
            _field("access_token", "Access token", secret=True, placeholder="sl.…"),
            _field("folder", "Folder path", required=False, placeholder="/notes"),
        ),
        "https://www.dropbox.com/developers/documentation/http/documentation",
        lambda v: DropboxConfig(_text(v, "access_token"), _text(v, "folder")),
        validate_dropbox,
        poll_dropbox,
        ("folder",),
    ),
    ConnectorDefinition(
        "linear",
        "Linear",
        "Issues and discussions from a Linear team.",
        (
            _field("api_key", "Personal API key", secret=True, placeholder="lin_api_…"),
            _field("team_id", "Team ID", required=False),
        ),
        "https://developers.linear.app/docs/graphql/working-with-the-graphql-api",
        lambda v: LinearConfig(_text(v, "api_key"), _text(v, "team_id")),
        validate_linear,
        poll_linear,
        ("team_id",),
    ),
    ConnectorDefinition(
        "trello",
        "Trello",
        "Boards, lists, and cards from Trello.",
        (
            _field("api_key", "API key", secret=True),
            _field("token", "Token", secret=True),
        ),
        "https://developer.atlassian.com/cloud/trello/guides/rest-api/api-introduction/",
        lambda v: TrelloConfig(_text(v, "api_key"), _text(v, "token")),
        validate_trello,
        poll_trello,
    ),
    ConnectorDefinition(
        "zendesk",
        "Zendesk",
        "Published Help Center articles from Zendesk.",
        (
            _field("subdomain", "Subdomain"),
            _field("email", "Agent email"),
            _field("api_token", "API token", secret=True),
        ),
        "https://support.zendesk.com/hc/en-us/articles/4408889192858-Managing-access-to-the-Zendesk-API",
        lambda v: ZendeskConfig(
            _text(v, "subdomain"), _text(v, "email"), _text(v, "api_token")
        ),
        validate_zendesk,
        poll_zendesk,
        ("subdomain",),
    ),
)

CONNECTOR_CATALOG: Mapping[str, ConnectorDefinition] = MappingProxyType(
    {definition.key: definition for definition in _DEFINITIONS}
)


def connector_definition(key: str) -> ConnectorDefinition:
    try:
        return CONNECTOR_CATALOG[key]
    except KeyError:
        raise KeyError(f"unknown connector: {key}") from None


def connector_definitions() -> tuple[ConnectorDefinition, ...]:
    return tuple(
        sorted(
            CONNECTOR_CATALOG.values(),
            key=lambda item: (item.priority, item.name.casefold()),
        )
    )
