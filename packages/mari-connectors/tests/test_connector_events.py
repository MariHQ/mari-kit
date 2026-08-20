from __future__ import annotations

import hashlib
import hmac
import json
import unittest

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
        slack = "v0=" + hmac.new(b"secret", b"v0:100:" + raw, hashlib.sha256).hexdigest()
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
            {"webhookEvent": "page_removed", "page": {"id": "9", "space": {"key": "ENG"}}}
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
        first = slack_change_hint({"event": {"type": "message", "channel": "C", "ts": "1"}})
        second = slack_change_hint({"event": {"type": "message", "channel": "C", "ts": "2", "thread_ts": "1"}})
        out = coalesce_hints([first, second])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].revision, "2")


if __name__ == "__main__":
    unittest.main()
