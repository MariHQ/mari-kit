"""Provider connector functions and shared polling helpers."""

from .airtable import AirtableConfig, poll_airtable, validate_airtable
from .asana import AsanaConfig, poll_asana, validate_asana
from .catalog import (
    CONNECTOR_CATALOG,
    ConnectorDefinition,
    ConnectorField,
    connector_definition,
    connector_definitions,
)
from .confluence import (
    ConfluenceConfig,
    fetch_confluence_page,
    poll_confluence,
    validate_confluence,
)
from .dropbox import DropboxConfig, poll_dropbox, validate_dropbox
from .github import (
    GitHubConfig,
    poll_github,
    validate_github,
)
from .google_drive import (
    GoogleDriveConfig,
    GoogleDriveWatch,
    poll_google_drive,
    poll_google_drive_changes,
    start_google_drive_watch,
    validate_google_drive,
)
from .jira import JiraConfig, poll_jira, validate_jira
from .linear import LinearConfig, poll_linear, validate_linear
from .notion import NotionConfig, poll_notion, validate_notion
from .protocol import (
    ConnectorMode,
    PollingConnector,
    StreamEvent,
    StreamingConnector,
    ValidationResult,
)
from .slack import SlackConfig, fetch_slack_thread_by_id, poll_slack, validate_slack
from .streaming import stream_change_hint, stream_pages
from .trello import TrelloConfig, poll_trello, validate_trello
from .zendesk import ZendeskConfig, poll_zendesk, validate_zendesk

__all__ = [
    "CONNECTOR_CATALOG",
    "AirtableConfig",
    "AsanaConfig",
    "ConfluenceConfig",
    "ConnectorDefinition",
    "ConnectorField",
    "ConnectorMode",
    "DropboxConfig",
    "GitHubConfig",
    "GoogleDriveConfig",
    "GoogleDriveWatch",
    "JiraConfig",
    "LinearConfig",
    "NotionConfig",
    "PollingConnector",
    "SlackConfig",
    "StreamEvent",
    "StreamingConnector",
    "TrelloConfig",
    "ValidationResult",
    "ZendeskConfig",
    "connector_definition",
    "connector_definitions",
    "fetch_confluence_page",
    "fetch_slack_thread_by_id",
    "poll_airtable",
    "poll_asana",
    "poll_confluence",
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
    "stream_change_hint",
    "stream_pages",
    "validate_airtable",
    "validate_asana",
    "validate_confluence",
    "validate_dropbox",
    "validate_github",
    "validate_google_drive",
    "validate_jira",
    "validate_linear",
    "validate_notion",
    "validate_slack",
    "validate_trello",
    "validate_zendesk",
]
