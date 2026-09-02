from __future__ import annotations

import unittest

from mari_components import KnowledgeDocument, PollPage, SyncMode, Tombstone
from mari_components.connectors import StreamEvent
from mari_components.testing import (
    check_connector_contract,
    check_streaming_connector_contract,
)


class ConnectorContractKitTests(unittest.TestCase):
    def test_reports_stable_replay_and_counts(self):
        pages = [
            PollPage(
                upserts=(
                    KnowledgeDocument(
                        source_id="fixture",
                        external_id="a",
                        title="A",
                        body="body",
                        revision="1",
                    ),
                ),
                tombstones=(Tombstone(source_id="fixture", external_id="b"),),
                next_cursor="v2",
                snapshot_complete=True,
            )
        ]
        first = check_connector_contract(
            pages, mode=SyncMode.INCREMENTAL, starting_cursor="v1"
        )
        second = check_connector_contract(
            pages, mode=SyncMode.INCREMENTAL, starting_cursor="v1"
        )
        self.assertEqual(first.replay_fingerprint, second.replay_fingerprint)
        self.assertEqual((first.upserts, first.tombstones), (1, 1))

    def test_rejects_cursor_advance_on_incomplete_page(self):
        with self.assertRaisesRegex(AssertionError, "advanced"):
            check_connector_contract(
                [PollPage(next_cursor="v2", snapshot_complete=False)],
                mode=SyncMode.FULL,
                starting_cursor="v1",
            )

    def test_streaming_contract_replays_through_the_same_page_rules(self):
        event = StreamEvent(
            provider="slack",
            raw_body=b'{"event":{"type":"message","channel":"C","ts":"1"}}',
        )

        def hydrate(hint):
            return (
                PollPage(
                    upserts=(
                        KnowledgeDocument(
                            source_id="slack:test",
                            external_id=hint.aggregate_key,
                            title="Thread",
                            body="Current thread",
                            revision=hint.revision,
                        ),
                    ),
                    snapshot_complete=True,
                ),
            )

        report = check_streaming_connector_contract(
            (event,), verify=lambda value: None, hydrate=hydrate
        )
        self.assertEqual((report.pages, report.upserts), (1, 1))
