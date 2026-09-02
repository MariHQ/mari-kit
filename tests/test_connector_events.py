from __future__ import annotations

import hashlib
import hmac
import json
import unittest

from mari_components import KnowledgeDocument, PollPage
from mari_components.connectors import StreamEvent, stream_change_hint, stream_pages
from mari_components.connectors.events import (
    coalesce_hints,
    confluence_change_hint,
    gdrive_change_hint,
    github_change_hint,
    slack_change_hint,
    verify_hmac_sha256,
    verify_slack_signature,
)
from mari_components.errors import AuthenticationFailure


class ConnectorEventTests(unittest.TestCase):
    def test_hmac_and_slack_replay_window(self):
        raw = b'{"ok":true}'
        signature = "sha256=" + hmac.new(b"secret", raw, hashlib.sha256).hexdigest()
        verify_hmac_sha256(raw, signature, "secret")
        slack = (
            "v0=" + hmac.new(b"secret", b"v0:100:" + raw, hashlib.sha256).hexdigest()
        )
        verify_slack_signature(raw, "100", slack, "secret", now=100)
        with self.assertRaises(AuthenticationFailure):
            verify_slack_signature(raw, "100", slack, "secret", now=1000)

    def test_provider_hints_are_bounded_and_canonical(self):
        github = github_change_hint(
            "push",
            {
                "repository": {"full_name": "MariHQ/mari"},
                "commits": [{"added": ["README.md"], "modified": [], "removed": []}],
            },
        )
        self.assertEqual(github.aggregate_key, "repository:marihq/mari")
        self.assertEqual(github.metadata["paths"], ("README.md",))
        confluence = confluence_change_hint(
            {
                "webhookEvent": "page_removed",
                "page": {"id": "9", "space": {"key": "ENG"}},
            }
        )
        self.assertTrue(confluence.deleted)
        drive = gdrive_change_hint(
            {
                "X-Goog-Channel-ID": "one",
                "X-Goog-Resource-ID": "resource",
                "X-Goog-Resource-State": "change",
                "X-Goog-Message-Number": "3",
            }
        )
        self.assertEqual(drive.revision, "3")
        slack = slack_change_hint(
            {"event": {"type": "message", "channel": "C1", "ts": "2", "thread_ts": "1"}}
        )
        self.assertEqual(slack.aggregate_key, "thread:C1:1")

    def test_coalescing_keeps_newest_hint(self):
        first = slack_change_hint(
            {"event": {"type": "message", "channel": "C", "ts": "1"}}
        )
        second = slack_change_hint(
            {"event": {"type": "message", "channel": "C", "ts": "2", "thread_ts": "1"}}
        )
        out = coalesce_hints([first, second])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].revision, "2")

    def test_stream_event_is_verified_before_parsing(self):
        calls = []
        event = StreamEvent(
            provider="github",
            event_type="push",
            raw_body=json.dumps(
                {"repository": {"full_name": "MariHQ/mari"}, "commits": []}
            ).encode(),
        )

        hint = stream_change_hint(event, verify=lambda value: calls.append(value))

        self.assertEqual(calls, [event])
        self.assertEqual(hint.aggregate_key, "repository:marihq/mari")

    def test_stream_pages_coalesces_then_hydrates_canonical_state(self):
        events = (
            StreamEvent(
                provider="slack",
                raw_body=b'{"event":{"type":"message","channel":"C","ts":"1"}}',
            ),
            StreamEvent(
                provider="slack",
                raw_body=b'{"event":{"type":"message","channel":"C","ts":"2","thread_ts":"1"}}',
            ),
        )
        hydrated = []

        def hydrate(hint):
            hydrated.append(hint)
            return (
                PollPage(
                    upserts=(
                        KnowledgeDocument(
                            source_id="slack:team",
                            external_id=hint.aggregate_key,
                            title="Thread",
                            body="Canonical provider state",
                            revision=hint.revision,
                        ),
                    ),
                    snapshot_complete=True,
                ),
            )

        pages = tuple(stream_pages(events, verify=lambda event: None, hydrate=hydrate))

        self.assertEqual(len(hydrated), 1)
        self.assertEqual(hydrated[0].revision, "2")
        self.assertEqual(pages[0].upserts[0].body, "Canonical provider state")

    def test_stream_batch_is_bounded(self):
        event = StreamEvent(
            provider="gdrive",
            headers={
                "X-Goog-Channel-ID": "one",
                "X-Goog-Resource-ID": "resource",
                "X-Goog-Resource-State": "change",
                "X-Goog-Message-Number": "1",
            },
        )
        with self.assertRaisesRegex(ValueError, "maximum_events"):
            tuple(
                stream_pages(
                    (event, event),
                    verify=lambda value: None,
                    hydrate=lambda hint: (),
                    maximum_events=1,
                )
            )


if __name__ == "__main__":
    unittest.main()
