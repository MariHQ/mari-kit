"""Provider connector functions and shared polling helpers."""

from .protocol import (
    ErrorKind,
    ValidationResult,
    call_with_retry,
    classify_error,
)
from .confluence import ConfluenceConfig, fetch_confluence_page, poll_confluence, validate_confluence
from .github import (
    GitHubConfig, github_blob, github_commits, github_head, github_issue_comments,
    github_issues, github_repository, github_tree, list_github_repositories,
    poll_github, validate_github, validate_github_team,
)
from .google_drive import (
    GoogleDriveConfig, GoogleDriveWatch, poll_google_drive,
    poll_google_drive_changes, start_google_drive_watch, validate_google_drive,
)
from .slack import SlackConfig, fetch_slack_thread_by_id, poll_slack, validate_slack
from .airtable import AirtableConfig, poll_airtable, validate_airtable
from .dropbox import DropboxConfig, poll_dropbox, validate_dropbox
from .jira import JiraConfig, poll_jira, validate_jira
from .asana import AsanaConfig, poll_asana, validate_asana
from .linear import LinearConfig, poll_linear, validate_linear
from .notion import NotionConfig, poll_notion, validate_notion
from .trello import TrelloConfig, poll_trello, validate_trello
from .zendesk import ZendeskConfig, poll_zendesk, validate_zendesk
from .catalog import (
    CONNECTOR_CATALOG, ConnectorDefinition, ConnectorField,
    connector_definition, connector_definitions,
)

__all__ = [
    "ConfluenceConfig",
    "CONNECTOR_CATALOG",
    "ConnectorDefinition",
    "ConnectorField",
    "AirtableConfig",
    "AsanaConfig",
    "DropboxConfig",
    "ErrorKind",
    "GitHubConfig",
    "GoogleDriveConfig",
    "GoogleDriveWatch",
    "JiraConfig",
    "LinearConfig",
    "NotionConfig",
    "SlackConfig",
    "TrelloConfig",
    "ValidationResult",
    "ZendeskConfig",
    "call_with_retry",
    "classify_error",
    "connector_definition",
    "connector_definitions",
    "fetch_confluence_page",
    "fetch_slack_thread_by_id",
    "github_blob",
    "github_commits",
    "github_head",
    "github_issue_comments",
    "github_issues",
    "github_repository",
    "github_tree",
    "list_github_repositories",
    "poll_confluence",
    "poll_airtable",
    "poll_asana",
    "poll_dropbox",
    "poll_github",
    "poll_google_drive",
    "poll_google_drive_changes",
    "poll_jira",
    "poll_linear",
    "poll_notion",
    "poll_slack",
    "poll_trello",
    "poll_zendesk",
    "start_google_drive_watch",
    "validate_confluence",
    "validate_airtable",
    "validate_asana",
    "validate_dropbox",
    "validate_github",
    "validate_github_team",
    "validate_google_drive",
    "validate_jira",
    "validate_linear",
    "validate_notion",
    "validate_slack",
    "validate_trello",
    "validate_zendesk",
]
