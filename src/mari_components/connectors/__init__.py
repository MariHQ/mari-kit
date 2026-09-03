"""Provider connector functions and shared polling helpers."""

from .airtable import AirtableConfig, poll_airtable, validate_airtable
from .asana import AsanaConfig, poll_asana, validate_asana
from .box import BoxConfig, poll_box, validate_box
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
from .events import HintCoalescingReport, coalesce_hints_ordered
from .filesystem import FilesystemConfig, poll_filesystem, validate_filesystem
from .github import (
    GitHubConfig,
    poll_github,
    validate_github,
)
from .gitlab import GitLabConfig, poll_gitlab, validate_gitlab
from .google_drive import (
    GoogleDriveConfig,
    GoogleDriveWatch,
    poll_google_drive,
    poll_google_drive_changes,
    start_google_drive_watch,
    validate_google_drive,
)
from .jira import JiraConfig, poll_jira, validate_jira
from .json_api import JSONAPIConfig, poll_json_api
from .linear import LinearConfig, poll_linear, validate_linear
from .microsoft_drive import (
    MicrosoftDriveConfig,
    poll_microsoft_drive,
    validate_microsoft_drive,
)
from .notion import NotionConfig, poll_notion, validate_notion
from .object_storage import (
    ObjectListing,
    ObjectStoreConfig,
    SourceObject,
    poll_object_store,
)
from .protocol import (
    ConnectorMode,
    PollingConnector,
    StreamEvent,
    StreamingConnector,
    ValidationResult,
)
from .rss import RSSConfig, poll_rss, validate_rss
from .singer import singer_pages
from .slack import SlackConfig, fetch_slack_thread_by_id, poll_slack, validate_slack
from .streaming import (
    HintHydrationIssue,
    HintHydrationReport,
    hydrate_hints,
    stream_change_hint,
    stream_hints,
    stream_pages,
    validate_hint_hydration,
)
from .trello import TrelloConfig, poll_trello, validate_trello
from .zendesk import ZendeskConfig, poll_zendesk, validate_zendesk

__all__ = [
    "CONNECTOR_CATALOG",
    "AirtableConfig",
    "AsanaConfig",
    "BoxConfig",
    "ConfluenceConfig",
    "ConnectorDefinition",
    "ConnectorField",
    "ConnectorMode",
    "DropboxConfig",
    "FilesystemConfig",
    "GitHubConfig",
    "GitLabConfig",
    "HintCoalescingReport",
    "HintHydrationIssue",
    "HintHydrationReport",
    "GoogleDriveConfig",
    "GoogleDriveWatch",
    "JiraConfig",
    "JSONAPIConfig",
    "LinearConfig",
    "MicrosoftDriveConfig",
    "NotionConfig",
    "ObjectListing",
    "ObjectStoreConfig",
    "PollingConnector",
    "RSSConfig",
    "SlackConfig",
    "StreamEvent",
    "StreamingConnector",
    "SourceObject",
    "TrelloConfig",
    "ValidationResult",
    "ZendeskConfig",
    "connector_definition",
    "connector_definitions",
    "coalesce_hints_ordered",
    "fetch_confluence_page",
    "fetch_slack_thread_by_id",
    "hydrate_hints",
    "poll_airtable",
    "poll_asana",
    "poll_box",
    "poll_confluence",
    "poll_dropbox",
    "poll_filesystem",
    "poll_github",
    "poll_gitlab",
    "poll_google_drive",
    "poll_google_drive_changes",
    "poll_jira",
    "poll_json_api",
    "poll_linear",
    "poll_microsoft_drive",
    "poll_notion",
    "poll_object_store",
    "poll_rss",
    "poll_slack",
    "poll_trello",
    "poll_zendesk",
    "start_google_drive_watch",
    "singer_pages",
    "stream_change_hint",
    "stream_hints",
    "stream_pages",
    "validate_airtable",
    "validate_asana",
    "validate_box",
    "validate_confluence",
    "validate_dropbox",
    "validate_filesystem",
    "validate_github",
    "validate_gitlab",
    "validate_hint_hydration",
    "validate_google_drive",
    "validate_jira",
    "validate_linear",
    "validate_microsoft_drive",
    "validate_notion",
    "validate_rss",
    "validate_slack",
    "validate_trello",
    "validate_zendesk",
]
