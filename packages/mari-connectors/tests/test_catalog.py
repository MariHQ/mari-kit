from __future__ import annotations

import unittest

from mari_components.connectors import CONNECTOR_CATALOG, connector_definitions


class CatalogTests(unittest.TestCase):
    def test_catalog_is_complete_unique_and_ordered(self):
        expected = {
            "airtable", "asana", "confluence", "dropbox", "gdrive", "github",
            "jira", "linear", "notion", "slack", "trello", "zendesk",
        }
        self.assertEqual(set(CONNECTOR_CATALOG), expected)
        ordered = connector_definitions()
        self.assertEqual([item.key for item in ordered[:6]], [
            "github", "slack", "gdrive", "confluence", "notion", "jira",
        ])
        self.assertTrue(all(definition.fields for definition in ordered))


if __name__ == "__main__":
    unittest.main()
