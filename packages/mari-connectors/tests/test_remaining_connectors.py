from __future__ import annotations

import json
import unittest

from mari_components.connectors.airtable import AirtableConfig, poll_airtable
from mari_components.connectors.dropbox import DropboxConfig, poll_dropbox
from mari_components.connectors.jira import JiraConfig, poll_jira
from mari_components.connectors.asana import AsanaConfig, poll_asana
from mari_components.connectors.linear import LinearConfig, poll_linear
from mari_components.connectors.notion import NotionConfig, poll_notion
from mari_components.connectors.trello import TrelloConfig, poll_trello
from mari_components.connectors.zendesk import ZendeskConfig, poll_zendesk
from mari_components.http import HttpResponse
from mari_components.types import PollRequest


class FakeHttp:
    def __init__(self, responses):
        self.responses = list(responses)

    def __call__(self, _request):
        if not self.responses:
            raise AssertionError("unexpected request")
        value = self.responses.pop(0)
        return value if isinstance(value, HttpResponse) else HttpResponse(200, {}, json.dumps(value).encode())


class RemainingConnectorTests(unittest.TestCase):
    def test_airtable_reads_all_record_pages(self):
        http = FakeHttp([
            {"tables": [{"id": "t1", "name": "Roadmap"}]},
            {"records": [{"id": "r1", "fields": {"Name": "One"}}], "offset": "next"},
            {"records": [{"id": "r2", "fields": {"Name": "Two"}}]},
        ])
        page = list(poll_airtable(AirtableConfig("token", "base"), PollRequest(page_size=1), http=http))[0]
        self.assertTrue(page.snapshot_complete)
        self.assertIn('"id": "r2"', page.upserts[0].body)

    def test_dropbox_native_tombstone(self):
        http = FakeHttp([{"entries": [{".tag": "deleted", "path_lower": "/gone.md"}], "cursor": "c1", "has_more": False}])
        page = list(poll_dropbox(DropboxConfig("token"), PollRequest(), http=http))[0]
        self.assertEqual(page.tombstones[0].external_id, "/gone.md")
        self.assertEqual(page.next_cursor, "c1")

    def test_jira_cursor_and_body(self):
        http = FakeHttp([{
            "total": 1,
            "issues": [{
                "key": "MARI-1",
                "fields": {"summary": "Ship", "description": {"content": [{"text": "Details"}]}, "updated": "2026-01-01"},
            }],
        }])
        page = list(poll_jira(JiraConfig("https://x.atlassian.net", "a@b.com", "token"), PollRequest(), http=http))[0]
        self.assertEqual(page.upserts[0].external_id, "MARI-1")
        self.assertEqual(page.next_cursor, "2026-01-01")

    def test_asana_task_cursor(self):
        http = FakeHttp([{"data": [{"gid": "t1", "name": "Ship", "notes": "Details", "modified_at": "2026-01-02"}]}])
        page = list(poll_asana(AsanaConfig("token", project_gid="p1"), PollRequest(), http=http))[0]
        self.assertEqual(page.upserts[0].external_id, "task:t1")
        self.assertEqual(page.next_cursor, "2026-01-02")

    def test_linear_graphql_pagination(self):
        http = FakeHttp([{"data": {"issues": {"nodes": [{"id": "i1", "identifier": "M-1", "title": "Ship", "description": "Body", "updatedAt": "2026-01-03", "comments": {"nodes": []}}], "pageInfo": {"hasNextPage": False}}}}])
        page = list(poll_linear(LinearConfig("key"), PollRequest(), http=http))[0]
        self.assertEqual(page.upserts[0].title, "M-1: Ship")

    def test_notion_page_and_blocks(self):
        http = FakeHttp([
            {"results": [{"id": "p1", "url": "https://notion.so/p1", "last_edited_time": "2026-01-04", "properties": {"Name": {"type": "title", "title": [{"plain_text": "Plan"}]}}}], "has_more": False},
            {"results": [{"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Body"}]}}], "has_more": False},
        ])
        page = list(poll_notion(NotionConfig("token"), PollRequest(), http=http))[0]
        self.assertEqual((page.upserts[0].title, page.upserts[0].body), ("Plan", "Body"))

    def test_trello_board_snapshot(self):
        http = FakeHttp([
            [{"id": "b1", "name": "Roadmap", "dateLastActivity": "2026-01-05", "url": "https://trello/b1"}],
            [{"id": "l1", "name": "Doing"}],
            [{"id": "c1", "name": "Ship", "desc": "Details", "idList": "l1"}],
        ])
        page = list(poll_trello(TrelloConfig("key", "token"), PollRequest(), http=http))[0]
        self.assertIn("List: Doing", page.upserts[0].body)

    def test_zendesk_article_cursor(self):
        http = FakeHttp([{"articles": [{"id": 1, "title": "Help", "body": "Answer", "updated_at": "2026-01-06"}], "next_page": None}])
        page = list(poll_zendesk(ZendeskConfig("acme", "a@b.com", "token"), PollRequest(), http=http))[0]
        self.assertEqual(page.upserts[0].external_id, "article:1")
        self.assertEqual(page.next_cursor, "2026-01-06")


if __name__ == "__main__":
    unittest.main()
