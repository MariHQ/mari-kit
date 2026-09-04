from __future__ import annotations

import json

import pytest

from mari_components import KnowledgeDocument, PollRequest
from mari_components.connectors import (
    BoxConfig,
    FilesystemConfig,
    GitHubConfig,
    GitLabConfig,
    JSONAPIConfig,
    MicrosoftDriveConfig,
    ObjectListing,
    ObjectStoreConfig,
    RSSConfig,
    SourceObject,
    connector_definition,
    github_source_id,
    poll_box,
    poll_filesystem,
    poll_gitlab,
    poll_json_api,
    poll_microsoft_drive,
    poll_object_store,
    poll_rss,
    singer_pages,
    stream_change_hint,
    stream_hints,
)
from mari_components.connectors.protocol import ConnectorMode, StreamEvent
from mari_components.errors import PermanentFailure
from mari_components.http import HttpRequest, HttpResponse


class QueueHttp:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        value = self.responses.pop(0)
        if isinstance(value, HttpResponse):
            return value
        return HttpResponse(200, {}, json.dumps(value).encode())


def test_configured_source_identity_changes_with_observed_scope() -> None:
    main = GitHubConfig("token", "acme/docs", branch="main", paths=("docs/**",))
    release = GitHubConfig("token", "acme/docs", branch="release", paths=("docs/**",))
    subset = GitHubConfig("token", "acme/docs", branch="main", paths=("README*",))
    assert (
        len(
            {
                github_source_id(main),
                github_source_id(release),
                github_source_id(subset),
            }
        )
        == 3
    )


def test_object_store_batch_is_sdk_neutral_bounded_and_checkpointed() -> None:
    listings = iter(
        (
            ObjectListing(
                objects=(SourceObject(key="docs/a.md", revision="1"),),
                next_cursor="page-2",
                complete=False,
            ),
            ObjectListing(
                objects=(SourceObject(key="docs/gone.md", revision="2", deleted=True),),
                next_cursor="done",
                complete=True,
            ),
        )
    )
    config = ObjectStoreConfig(provider="s3", container="knowledge", prefix="docs/")

    pages = tuple(
        poll_object_store(
            config,
            PollRequest(page_size=10),
            list_objects=lambda _config, _cursor, _limit: next(listings),
            read_object=lambda _config, item: f"body:{item.key}".encode(),
        )
    )

    assert pages[0].next_checkpoint == "page-2"
    assert pages[0].upserts[0].source_id == "s3:knowledge"
    assert pages[1].tombstones[0].external_id == "docs/gone.md"
    assert pages[1].snapshot_complete


def test_singer_bridge_pages_records_and_surfaces_state() -> None:
    messages = [
        {"type": "SCHEMA", "stream": "articles", "schema": {}},
        {"type": "RECORD", "stream": "articles", "record": {"id": "1"}},
        {"type": "STATE", "value": {"updated_at": "2026-01-01"}},
    ]

    pages = tuple(
        singer_pages(
            messages,
            document=lambda stream, row: KnowledgeDocument(
                source_id=f"singer:{stream}",
                external_id=row["id"],
                title=row["id"],
                body=json.dumps(row),
                revision="1",
            ),
        )
    )

    assert pages[-1].upserts[0].external_id == "1"
    assert pages[-1].next_cursor == '{"updated_at":"2026-01-01"}'


def test_rss_batch_parses_atom_and_emits_conditional_cursor() -> None:
    feed = b"""<feed xmlns="http://www.w3.org/2005/Atom">
      <title>Engineering</title><entry><id>post-1</id><title>Release</title>
      <updated>2026-01-01T00:00:00Z</updated><link href="https://e/p/1" />
      <content>Details</content></entry></feed>"""
    http = QueueHttp([HttpResponse(200, {"ETag": '"v1"'}, feed)])

    page = tuple(poll_rss(RSSConfig("https://e/feed"), PollRequest(), http=http))[0]

    assert page.upserts[0].body == "Details"
    assert page.upserts[0].external_id == "post-1"
    assert json.loads(page.next_cursor or "{}")["etag"] == '"v1"'


def test_gitlab_batch_uses_head_as_cursor_and_reads_matching_files() -> None:
    http = QueueHttp(
        [
            {"id": 7, "path_with_namespace": "acme/docs", "default_branch": "main"},
            {"commit": {"id": "head-1"}},
            HttpResponse(
                200,
                {"X-Next-Page": ""},
                json.dumps(
                    [{"id": "blob-1", "type": "blob", "path": "README.md", "size": 4}]
                ).encode(),
            ),
            HttpResponse(200, {}, b"body"),
        ]
    )

    page = tuple(
        poll_gitlab(GitLabConfig("token", "acme/docs"), PollRequest(), http=http)
    )[0]

    assert page.next_cursor == "head-1"
    assert page.upserts[0].metadata["provider_revision"] == "blob-1"
    assert page.upserts[0].revision.startswith("sha256:")
    assert page.upserts[0].body == "body"


def test_microsoft_drive_delta_normalizes_files_and_tombstones() -> None:
    http = QueueHttp(
        [
            {
                "value": [
                    {
                        "id": "f1",
                        "name": "Guide.md",
                        "size": 4,
                        "file": {"mimeType": "text/markdown"},
                        "eTag": "etag-1",
                        "lastModifiedDateTime": "2026-01-01T00:00:00Z",
                    },
                    {"id": "gone", "deleted": {}},
                ],
                "@odata.deltaLink": "https://graph.microsoft.com/v1.0/drives/drive-1/delta?token=1",
            },
            HttpResponse(200, {}, b"body"),
        ]
    )

    page = tuple(
        poll_microsoft_drive(
            MicrosoftDriveConfig("token", "drive-1"), PollRequest(), http=http
        )
    )[0]

    assert page.next_cursor.endswith("delta?token=1")
    assert page.upserts[0].source_id == "onedrive:drive-1"
    assert page.tombstones[0].external_id == "gone"


def test_box_batch_uses_marker_pagination() -> None:
    http = QueueHttp(
        [
            {
                "entries": [
                    {
                        "id": "f1",
                        "type": "file",
                        "name": "Guide.md",
                        "sha1": "sha",
                        "size": 4,
                        "modified_at": "2026-01-01T00:00:00Z",
                    }
                ]
            },
            HttpResponse(200, {}, b"body"),
        ]
    )

    page = tuple(poll_box(BoxConfig("token"), PollRequest(), http=http))[0]

    assert page.snapshot_complete
    assert page.upserts[0].body == "body"


def test_streaming_expansion_emits_hints_without_checkpoint_state() -> None:
    events = (
        StreamEvent(
            provider="gitlab",
            raw_body=json.dumps(
                {
                    "object_kind": "push",
                    "project": {"path_with_namespace": "acme/docs"},
                    "after": "head",
                    "commits": [{"modified": ["README.md"]}],
                }
            ).encode(),
        ),
        StreamEvent(
            provider="s3",
            raw_body=json.dumps(
                {
                    "Records": [
                        {
                            "eventName": "ObjectCreated:Put",
                            "s3": {
                                "bucket": {"name": "knowledge"},
                                "object": {"key": "docs/a.md", "eTag": "1"},
                            },
                        }
                    ]
                }
            ).encode(),
        ),
    )

    hints = tuple(stream_hints(events, verify=lambda event: None))

    assert [(hint.provider, hint.aggregate_key) for hint in hints] == [
        ("gitlab", "project:acme/docs"),
        ("s3", "container:knowledge"),
    ]
    assert hints[1].external_id == "docs/a.md"


def test_catalog_exposes_new_batch_and_stream_modes() -> None:
    assert connector_definition("rss").modes == {ConnectorMode.POLL}
    assert connector_definition("gitlab").modes == {
        ConnectorMode.POLL,
        ConnectorMode.STREAM,
    }
    assert connector_definition("onedrive").supports(ConnectorMode.STREAM)
    assert connector_definition("sharepoint").supports(ConnectorMode.STREAM)
    assert connector_definition("box").supports(ConnectorMode.STREAM)
    assert connector_definition("filesystem").modes == {ConnectorMode.POLL}


def test_gitlab_authentication_header_is_redacted() -> None:
    request = HttpRequest("GET", "https://gitlab.test/api", {"PRIVATE-TOKEN": "secret"})

    assert "secret" not in repr(request)


def test_filesystem_batch_has_stable_snapshot_and_bounded_pages(tmp_path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("alpha")
    (docs / "b.txt").write_text("beta")
    (docs / "ignored.bin").write_bytes(b"binary")

    pages = tuple(
        poll_filesystem(
            FilesystemConfig(tmp_path), PollRequest(page_size=1, page_limit=3)
        )
    )

    assert [page.upserts[0].external_id for page in pages] == [
        "docs/a.md",
        "docs/b.txt",
    ]
    assert pages[-1].snapshot_complete
    assert pages[-1].next_cursor


def test_cloudevents_are_checkpoint_free_dirty_hints() -> None:
    event = StreamEvent(
        provider="cloudevents",
        raw_body=json.dumps(
            {
                "specversion": "1.0",
                "id": "event-1",
                "source": "/crm/accounts",
                "type": "account.updated",
                "subject": "account-7",
                "data": {"revision": "3"},
            }
        ).encode(),
    )

    hint = tuple(stream_hints((event,), verify=lambda value: None))[0]

    assert hint.aggregate_key == "/crm/accounts:account-7"
    assert hint.revision == "3"
    assert not hasattr(hint, "checkpoint")


@pytest.mark.parametrize(
    ("provider", "payload", "aggregate"),
    [
        (
            "box",
            {"trigger": "FILE.UPLOADED", "source": {"id": "f1", "type": "file"}},
            "item:f1",
        ),
        (
            "onedrive",
            {
                "value": [
                    {
                        "subscriptionId": "s1",
                        "changeType": "updated",
                        "resource": "drives/d/items/f1",
                        "resourceData": {"id": "f1"},
                    }
                ]
            },
            "subscription:s1",
        ),
        (
            "sharepoint",
            {
                "value": [
                    {
                        "subscriptionId": "s2",
                        "changeType": "deleted",
                        "resource": "drives/d/items/f2",
                        "resourceData": {"id": "f2"},
                    }
                ]
            },
            "subscription:s2",
        ),
        (
            "gcs",
            {"bucket": "knowledge", "name": "docs/a.md", "type": "finalized"},
            "container:knowledge",
        ),
        (
            "azure_blob",
            {
                "eventType": "Microsoft.Storage.BlobCreated",
                "subject": "/blobServices/default/containers/knowledge/blobs/docs/a.md",
                "data": {"eTag": "1"},
            },
            "container:knowledge",
        ),
    ],
)
def test_each_new_provider_event_has_a_canonical_aggregate(
    provider, payload, aggregate
) -> None:
    hint = stream_change_hint(
        StreamEvent(provider=provider, raw_body=json.dumps(payload).encode()),
        verify=lambda value: None,
    )

    assert hint.aggregate_key == aggregate


def test_json_api_bridge_bounds_pages_and_keeps_same_origin_continuations() -> None:
    http = QueueHttp([{"rows": [{"id": "1"}], "paging": {"next": "/page/2"}}])
    config = JSONAPIConfig(
        url="https://api.example.test/page/1",
        records_path=("rows",),
        next_path=("paging", "next"),
    )

    page = next(
        poll_json_api(
            config,
            PollRequest(page_limit=1),
            http=http,
            document=lambda row: KnowledgeDocument(
                source_id="json:example",
                external_id=row["id"],
                title=row["id"],
                body=json.dumps(row),
                revision="1",
            ),
        )
    )

    assert page.next_checkpoint == "https://api.example.test/page/2"


def test_json_api_bridge_rejects_cross_origin_continuations() -> None:
    http = QueueHttp([{"rows": [], "next": "https://attacker.test/steal"}])

    with pytest.raises(PermanentFailure, match="origin"):
        tuple(
            poll_json_api(
                JSONAPIConfig(
                    url="https://api.example.test/page", records_path=("rows",)
                ),
                PollRequest(),
                http=http,
                document=lambda row: None,
            )
        )
