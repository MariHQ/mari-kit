from __future__ import annotations

import base64
import json
import unittest
import urllib.parse

from mari_components.connectors.confluence import (
    ConfluenceConfig,
    poll_confluence,
    storage_to_text,
    validate_confluence,
)
from mari_components.connectors.google_drive import GoogleDriveConfig, poll_google_drive
from mari_components.connectors.google_drive import start_google_drive_watch
from mari_components.connectors.github import (
    GitHubConfig, list_github_repositories, poll_github, validate_github_team,
)
from mari_components.connectors.slack import SlackConfig, fetch_slack_thread_by_id, poll_slack
from mari_components.http import HttpResponse
from mari_components.types import PollRequest, SyncMode


class FakeHttp:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        if not self.responses:
            raise AssertionError(f"unexpected request: {request.url}")
        value = self.responses.pop(0)
        return value if isinstance(value, HttpResponse) else HttpResponse(200, {}, json.dumps(value).encode())


class PriorityConnectorTests(unittest.TestCase):
    def test_github_team_validation_is_a_reusable_connector_operation(self):
        http = FakeHttp([{"slug": "docs"}])
        result = validate_github_team("token", "MariHQ", "docs", http=http)
        self.assertTrue(result.ok)
        self.assertEqual(result.identity, "MariHQ/docs")
        self.assertIn("/orgs/MariHQ/teams/docs", http.requests[0].url)

    def test_confluence_validation_and_ordered_checkpoint(self):
        config = ConfluenceConfig("https://example.atlassian.net", "me@example.com", "secret")
        validating = FakeHttp([{"results": []}])
        self.assertTrue(validate_confluence(config, http=validating).ok)
        auth = validating.requests[0].headers["Authorization"].removeprefix("Basic ")
        self.assertEqual(base64.b64decode(auth).decode(), "me@example.com:secret")
        polling = FakeHttp(
            [
                {
                    "size": 1,
                    "results": [
                        {
                            "id": "2",
                            "title": "Two",
                            "body": {"storage": {"value": "<h1>Hi</h1><p>Body</p>"}},
                            "version": {"number": 3},
                            "history": {"lastUpdated": {"when": "2026-01-02T00:00:00Z"}},
                        }
                    ],
                }
            ]
        )
        pages = list(poll_confluence(config, PollRequest(page_size=2), http=polling))
        self.assertTrue(pages[0].snapshot_complete)
        self.assertEqual(pages[0].upserts[0].body, "# Hi\nBody")
        self.assertEqual(pages[0].next_cursor, "2026-01-02T00:00:00Z|2")

    def test_google_drive_snapshot_then_changes_tombstone(self):
        config = GoogleDriveConfig("token")
        initial = FakeHttp(
            [
                {"startPageToken": "start"},
                {
                    "files": [
                        {
                            "id": "d1",
                            "name": "Doc",
                            "mimeType": "application/vnd.google-apps.document",
                            "modifiedTime": "2026-01-01T00:00:00Z",
                            "permissions": [{"type": "group", "emailAddress": "Eng@Example.com"}],
                        }
                    ]
                },
                HttpResponse(200, {}, b"Document body"),
            ]
        )
        pages = list(poll_google_drive(config, PollRequest(mode=SyncMode.FULL), http=initial))
        self.assertEqual(pages[0].next_cursor, "changes:start")
        self.assertEqual(pages[0].upserts[0].acl.principals[0].identifier, "eng@example.com")
        changes = FakeHttp([{"changes": [{"fileId": "d1", "removed": True}], "newStartPageToken": "next"}])
        pages = list(
            poll_google_drive(config, PollRequest(cursor="changes:start"), http=changes)
        )
        self.assertEqual(pages[0].tombstones[0].external_id, "d1")
        self.assertEqual(pages[0].next_cursor, "changes:next")

    def test_storage_conversion(self):
        self.assertEqual(storage_to_text("<ul><li>One</li><li>Two</li></ul>"), "- One\n- Two")

    def test_github_repo_discovery_and_file_deletion(self):
        discovery = FakeHttp([[{"full_name": "MariHQ/mari"}]])
        self.assertEqual(list_github_repositories("token", http=discovery)[0]["full_name"], "MariHQ/mari")
        old_cursor = json.dumps({"head": "old", "item_since": "", "files": {"gone.md": "1"}})
        api = FakeHttp(
            [
                {"full_name": "MariHQ/mari", "default_branch": "main"},
                {"sha": "head", "commit": {"committer": {"date": "2026-08-19T18:42:07-07:00"}}},
            {"truncated": False, "tree": [
                {"type": "blob", "path": "README.md", "sha": "blob"},
                {"type": "blob", "path": "src/app.ts", "sha": "typescript"},
            ]},
                {"content": base64.b64encode(b"# Mari").decode()},
                [],
                [],
            ]
        )
        page = list(poll_github(GitHubConfig("token", "MariHQ/mari"), PollRequest(cursor=old_cursor), http=api))[0]
        self.assertTrue(page.snapshot_complete)
        self.assertEqual(page.upserts[0].external_id, "file:README.md")
        self.assertNotIn("src/app.ts", json.loads(page.next_cursor)["files"])
        self.assertEqual(page.upserts[0].updated_at, "2026-08-20T01:42:07Z")
        self.assertEqual(page.tombstones[0].external_id, "file:gone.md")

    def test_github_path_filters_are_connector_configuration(self):
        api = FakeHttp([
            {"full_name": "owner/repo", "default_branch": "main"},
            {"sha": "head", "commit": {"author": {"date": "2026-08-20T01:42:07Z"}}},
            {"truncated": False, "tree": [
                {"type": "blob", "path": "docs/guide.md", "sha": "one"},
                {"type": "blob", "path": "src/app.py", "sha": "two"},
            ]},
            {"content": base64.b64encode(b"Guide").decode()},
            [],
            [],
        ])
        page = list(poll_github(
            GitHubConfig("token", "owner/repo", paths=("docs/**",)),
            PollRequest(), http=api,
        ))[0]
        self.assertEqual([document.external_id for document in page.upserts],
                         ["file:docs/guide.md"])

    def test_slack_channel_root_is_restricted_and_incremental(self):
        api = FakeHttp(
            [
                {"ok": True, "members": [{"id": "U1", "name": "Dana"}]},
                {"ok": True, "channels": [{"id": "C1", "name": "product", "is_member": True}]},
                {"ok": True, "messages": [{"type": "message", "ts": "2.0", "user": "U1", "text": "Roadmap"}]},
            ]
        )
        page = list(poll_slack(SlackConfig("xoxb-token"), PollRequest(), http=api))[0]
        self.assertTrue(page.snapshot_complete)
        self.assertEqual(page.upserts[0].acl.principals[0].identifier, "C1")
        self.assertEqual(page.next_cursor, "2.000000")
        params = urllib.parse.parse_qs((api.requests[1].body or b"").decode())
        self.assertEqual(params["types"], ["public_channel,private_channel"])

    def test_slack_polling_refetches_root_for_a_new_reply_row(self):
        api = FakeHttp([
            {"ok": True, "members": [{"id": "U1", "name": "Dana"}]},
            {"ok": True, "channels": [{"id": "C1", "name": "product", "is_member": True}]},
            {"ok": True, "messages": [{
                "type": "message", "ts": "3.0", "thread_ts": "1.0",
                "user": "U1", "text": "New reply",
            }]},
            {"ok": True, "messages": [
                {"type": "message", "ts": "1.0", "user": "U1", "text": "Question"},
                {"type": "message", "ts": "3.0", "thread_ts": "1.0", "user": "U1", "text": "New reply"},
            ]},
        ])
        page = list(poll_slack(
            SlackConfig("xoxb-token"), PollRequest(cursor="2.000000"), http=api,
        ))[0]
        self.assertEqual([document.external_id for document in page.upserts], ["thread:C1:1.0"])
        self.assertIn("New reply", page.upserts[0].body)
        self.assertEqual(page.next_cursor, "3.000000")

    def test_event_helpers_refetch_canonical_slack_thread_and_create_drive_watch(self):
        slack = FakeHttp([
            {"ok": True, "members": [{"id": "U1", "name": "Dana"}]},
            {"ok": True, "messages": [
                {"type": "message", "ts": "1.0", "user": "U1", "text": "Question"},
                {"type": "message", "ts": "2.0", "thread_ts": "1.0", "user": "U1", "text": "Answer"},
            ]},
        ])
        document, complete = fetch_slack_thread_by_id(
            SlackConfig("xoxb-token", history_token="xoxp-token"), "C1", "1.0", http=slack,
        )
        self.assertTrue(complete)
        self.assertEqual(document.external_id, "thread:C1:1.0")
        self.assertIn("Answer", document.body)

        drive = FakeHttp([{"id": "channel", "resourceId": "resource", "expiration": "123"}])
        watch = start_google_drive_watch(
            GoogleDriveConfig("token"), "page", "https://kb.example/webhooks/drive",
            "channel", "secret", http=drive, expiration_ms=100,
        )
        self.assertEqual(watch.resource_id, "resource")
        self.assertEqual(watch.expiration_ms, 123)
        request = drive.requests[0]
        self.assertNotIn("secret", request.url)
        self.assertEqual(json.loads(request.body)["token"], "secret")


if __name__ == "__main__":
    unittest.main()
