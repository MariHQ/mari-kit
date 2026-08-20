from __future__ import annotations

import unittest

from mari_components import KnowledgeDocument, PollPage, SyncMode, Tombstone
from mari_components.testing import check_connector_contract


class ConnectorContractKitTests(unittest.TestCase):
    def test_reports_stable_replay_and_counts(self):
        pages = [PollPage(
            upserts=(KnowledgeDocument("a", "A", "body"),),
            tombstones=(Tombstone("b"),),
            next_cursor="v2", snapshot_complete=True,
        )]
        first = check_connector_contract(pages, mode=SyncMode.INCREMENTAL, starting_cursor="v1")
        second = check_connector_contract(pages, mode=SyncMode.INCREMENTAL, starting_cursor="v1")
        self.assertEqual(first.replay_fingerprint, second.replay_fingerprint)
        self.assertEqual((first.upserts, first.tombstones), (1, 1))

    def test_rejects_cursor_advance_on_incomplete_page(self):
        with self.assertRaisesRegex(AssertionError, "advanced"):
            check_connector_contract(
                [PollPage(next_cursor="v2", snapshot_complete=False)],
                mode=SyncMode.FULL, starting_cursor="v1",
            )
