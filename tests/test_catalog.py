from __future__ import annotations

import unittest

from mari_components.connectors import CONNECTOR_CATALOG, connector_definitions
from mari_components.connectors.airtable import AirtableConfig
from mari_components.connectors.asana import AsanaConfig
from mari_components.connectors.confluence import ConfluenceConfig
from mari_components.connectors.dropbox import DropboxConfig
from mari_components.connectors.github import GitHubConfig
from mari_components.connectors.google_drive import (
    GoogleDriveConfig,
    GoogleOAuthRefresh,
)
from mari_components.connectors.jira import JiraConfig
from mari_components.connectors.linear import LinearConfig
from mari_components.connectors.notion import NotionConfig
from mari_components.connectors.slack import SlackConfig
from mari_components.connectors.trello import TrelloConfig
from mari_components.connectors.zendesk import ZendeskConfig


class CatalogTests(unittest.TestCase):
    def test_catalog_is_complete_unique_and_ordered(self):
        expected = {
            "airtable",
            "asana",
            "confluence",
            "dropbox",
            "gdrive",
            "github",
            "jira",
            "linear",
            "notion",
            "slack",
            "trello",
            "zendesk",
        }
        self.assertEqual(set(CONNECTOR_CATALOG), expected)
        ordered = connector_definitions()
        self.assertEqual(
            [item.key for item in ordered[:6]],
            [
                "github",
                "slack",
                "gdrive",
                "confluence",
                "notion",
                "jira",
            ],
        )
        self.assertTrue(all(definition.fields for definition in ordered))

    def test_connector_credentials_are_absent_from_representations(self):
        secret = "recognizable-secret-value"
        configs = (
            AirtableConfig(secret, "base"),
            AsanaConfig(secret),
            ConfluenceConfig("https://example.com", "owner@example.com", secret),
            DropboxConfig(secret),
            GitHubConfig(secret, "owner/repo"),
            GoogleDriveConfig(secret),
            GoogleOAuthRefresh(secret, "client", secret),
            JiraConfig("https://example.com", "owner@example.com", secret),
            LinearConfig(secret),
            NotionConfig(secret),
            SlackConfig(secret, history_token=secret),
            TrelloConfig(secret, secret),
            ZendeskConfig("acme", "owner@example.com", secret),
        )
        self.assertTrue(all(secret not in repr(config) for config in configs))


if __name__ == "__main__":
    unittest.main()
