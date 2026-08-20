"""Declarative connector catalog and raw-configuration adapters.

The catalog is application-neutral: labels describe provider credentials, not
screens or database columns. Applications may render it, filter it, or replace
individual definitions without maintaining parallel config/validate/poll maps.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Iterator, Mapping

from mari_components.http import HttpTransport
from mari_components.errors import AuthenticationFailure
from mari_components.types import PollPage, PollRequest
from .airtable import AirtableConfig, poll_airtable, validate_airtable
from .asana import AsanaConfig, poll_asana, validate_asana
from .confluence import ConfluenceConfig, poll_confluence, validate_confluence
from .dropbox import DropboxConfig, poll_dropbox, validate_dropbox
from .github import GitHubConfig, poll_github, validate_github
from .google_drive import (
    GoogleDriveConfig, GoogleOAuthRefresh, poll_google_drive,
    refresh_google_access_token, validate_google_drive,
)
from .jira import JiraConfig, poll_jira, validate_jira
from .linear import LinearConfig, poll_linear, validate_linear
from .notion import NotionConfig, poll_notion, validate_notion
from .protocol import ValidationResult
from .slack import SlackConfig, poll_slack, validate_slack
from .trello import TrelloConfig, poll_trello, validate_trello
from .zendesk import ZendeskConfig, poll_zendesk, validate_zendesk


ConfigFactory = Callable[[Mapping[str, Any]], Any]
ValidateOperation = Callable[..., ValidationResult]
PollOperation = Callable[..., Iterator[PollPage]]
RefreshOperation = Callable[[Mapping[str, Any], HttpTransport], Any]


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

    def config(self, values: Mapping[str, Any]) -> Any:
        return self.config_factory(values)

    def validate(self, values: Mapping[str, Any], *, http: HttpTransport) -> ValidationResult:
        result = self.validate_operation(self.config(values), http=http)
        if result.ok or self.refresh_operation is None or not _has_refresh(values):
            return result
        return self.validate_operation(self.refresh_operation(values, http), http=http)

    def poll(
        self, values: Mapping[str, Any], request: PollRequest, *, http: HttpTransport,
    ) -> Iterator[PollPage]:
        try:
            yield from self.poll_operation(self.config(values), request, http=http)
        except AuthenticationFailure:
            if self.refresh_operation is None or not _has_refresh(values):
                raise
            yield from self.poll_operation(self.refresh_operation(values, http), request, http=http)


def _text(values: Mapping[str, Any], key: str) -> str:
    return str(values.get(key) or "").strip()


def _has_refresh(values: Mapping[str, Any]) -> bool:
    return all(_text(values, key) for key in ("refresh_token", "client_id", "client_secret"))


def _refresh_drive(values: Mapping[str, Any], http: HttpTransport) -> GoogleDriveConfig:
    token = refresh_google_access_token(
        GoogleOAuthRefresh(
            _text(values, "refresh_token"), _text(values, "client_id"),
            _text(values, "client_secret"),
        ),
        http=http,
    )
    return GoogleDriveConfig(token, _text(values, "folder_id"))


def _field(
    key: str, label: str, *, secret: bool = False, required: bool = True,
    placeholder: str = "", help: str = "",
) -> ConnectorField:
    return ConnectorField(key, label, secret, required, placeholder, help)


_DEFINITIONS = (
    ConnectorDefinition(
        "github", "GitHub", "Markdown, issues, pull requests, and commits from a repository.",
        (
            _field("token", "Fine-grained personal access token", secret=True, placeholder="github_pat_…"),
            _field("repo", "Repository", placeholder="owner/repository"),
            _field("branch", "Branch", required=False, placeholder="main"),
            _field("paths", "Paths filter", required=False, placeholder="docs/**"),
        ),
        "https://github.com/settings/personal-access-tokens/new",
        lambda v: GitHubConfig(
            _text(v, "token"), _text(v, "repo"), _text(v, "branch"),
            tuple(part.strip() for part in _text(v, "paths").replace("\n", ",").split(",")
                  if part.strip()),
        ),
        validate_github, poll_github, ("repo",), 10,
    ),
    ConnectorDefinition(
        "slack", "Slack", "Threaded channel history visible to the installed application.",
        (
            _field("bot_token", "Bot token", secret=True, placeholder="xoxb-…"),
            _field("history_token", "User history token", secret=True, required=False, placeholder="xoxp-…"),
            _field("channels", "Channels", required=False, placeholder="general, engineering"),
        ),
        "https://api.slack.com/tutorials/tracks/getting-a-token",
        lambda v: SlackConfig(
            _text(v, "bot_token"),
            tuple(item.strip() for item in _text(v, "channels").split(",") if item.strip()),
            _text(v, "history_token"),
        ),
        validate_slack, poll_slack, ("channels",), 20,
    ),
    ConnectorDefinition(
        "gdrive", "Google Drive", "Google Docs and text files, including native change tracking.",
        (
            _field("access_token", "OAuth access token", secret=True, placeholder="ya29.…"),
            _field("refresh_token", "OAuth refresh token", secret=True, required=False, placeholder="1//…"),
            _field("client_id", "OAuth client ID", required=False),
            _field("client_secret", "OAuth client secret", secret=True, required=False),
            _field("folder_id", "Folder ID", required=False),
        ),
        "https://developers.google.com/drive/api/guides/about-sdk",
        lambda v: GoogleDriveConfig(_text(v, "access_token"), _text(v, "folder_id")),
        validate_google_drive, poll_google_drive, ("folder_id",), 30, _refresh_drive,
    ),
    ConnectorDefinition(
        "confluence", "Confluence", "Pages from readable Confluence spaces.",
        (
            _field("site_url", "Site URL", placeholder="https://company.atlassian.net"),
            _field("email", "Atlassian account email"),
            _field("api_token", "API token", secret=True, placeholder="ATATT…"),
            _field("space_key", "Space key", required=False, placeholder="ENG"),
            _field("webhook_secret", "Webhook signing secret", secret=True, required=False),
        ),
        "https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/",
        lambda v: ConfluenceConfig(
            _text(v, "site_url"), _text(v, "email"), _text(v, "api_token"),
            _text(v, "space_key"),
        ),
        validate_confluence, poll_confluence, ("site_url", "space_key"), 40,
    ),
    ConnectorDefinition(
        "notion", "Notion", "Pages shared with a Notion integration.",
        (_field("token", "Internal integration token", secret=True, placeholder="ntn_…"),),
        "https://developers.notion.com/docs/create-a-notion-integration",
        lambda v: NotionConfig(_text(v, "token")), validate_notion, poll_notion, priority=50,
    ),
    ConnectorDefinition(
        "jira", "Jira", "Issues and discussions selected by a JQL query.",
        (
            _field("site_url", "Site URL", placeholder="https://company.atlassian.net"),
            _field("email", "Atlassian account email"),
            _field("api_token", "API token", secret=True, placeholder="ATATT…"),
            _field("project_key", "Project key", required=False),
            _field("jql", "JQL filter", required=False),
        ),
        "https://developer.atlassian.com/cloud/jira/platform/rest/v3/",
        lambda v: JiraConfig(
            _text(v, "site_url"), _text(v, "email"), _text(v, "api_token"),
            _text(v, "project_key"), _text(v, "jql"),
        ),
        validate_jira, poll_jira, ("site_url", "project_key"), 60,
    ),
    ConnectorDefinition(
        "airtable", "Airtable", "Tables and records from an Airtable base.",
        (
            _field("pat", "Personal access token", secret=True, placeholder="pat…"),
            _field("base_id", "Base ID", placeholder="appXXXXXXXXXXXXXX"),
        ),
        "https://airtable.com/developers/web/api/introduction",
        lambda v: AirtableConfig(_text(v, "pat"), _text(v, "base_id")),
        validate_airtable, poll_airtable, ("base_id",),
    ),
    ConnectorDefinition(
        "asana", "Asana", "Projects and tasks from an Asana workspace.",
        (
            _field("pat", "Personal access token", secret=True),
            _field("workspace", "Workspace GID", required=False),
            _field("project_gid", "Project GID", required=False),
        ),
        "https://developers.asana.com/docs/personal-access-token",
        lambda v: AsanaConfig(_text(v, "pat"), _text(v, "workspace"), _text(v, "project_gid")),
        validate_asana, poll_asana, ("workspace", "project_gid"),
    ),
    ConnectorDefinition(
        "dropbox", "Dropbox", "Text and Markdown documents from a Dropbox folder.",
        (
            _field("access_token", "Access token", secret=True, placeholder="sl.…"),
            _field("folder", "Folder path", required=False, placeholder="/notes"),
        ),
        "https://www.dropbox.com/developers/documentation/http/documentation",
        lambda v: DropboxConfig(_text(v, "access_token"), _text(v, "folder")),
        validate_dropbox, poll_dropbox, ("folder",),
    ),
    ConnectorDefinition(
        "linear", "Linear", "Issues and discussions from a Linear team.",
        (
            _field("api_key", "Personal API key", secret=True, placeholder="lin_api_…"),
            _field("team_id", "Team ID", required=False),
        ),
        "https://developers.linear.app/docs/graphql/working-with-the-graphql-api",
        lambda v: LinearConfig(_text(v, "api_key"), _text(v, "team_id")),
        validate_linear, poll_linear, ("team_id",),
    ),
    ConnectorDefinition(
        "trello", "Trello", "Boards, lists, and cards from Trello.",
        (
            _field("api_key", "API key", secret=True),
            _field("token", "Token", secret=True),
        ),
        "https://developer.atlassian.com/cloud/trello/guides/rest-api/api-introduction/",
        lambda v: TrelloConfig(_text(v, "api_key"), _text(v, "token")),
        validate_trello, poll_trello,
    ),
    ConnectorDefinition(
        "zendesk", "Zendesk", "Published Help Center articles from Zendesk.",
        (
            _field("subdomain", "Subdomain"),
            _field("email", "Agent email"),
            _field("api_token", "API token", secret=True),
        ),
        "https://support.zendesk.com/hc/en-us/articles/4408889192858-Managing-access-to-the-Zendesk-API",
        lambda v: ZendeskConfig(_text(v, "subdomain"), _text(v, "email"), _text(v, "api_token")),
        validate_zendesk, poll_zendesk, ("subdomain",),
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
    return tuple(sorted(CONNECTOR_CATALOG.values(), key=lambda item: (item.priority, item.name.casefold())))
