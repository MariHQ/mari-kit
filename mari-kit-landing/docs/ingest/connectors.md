[]{#connectors}[Current]{.current-label}

# Polling and streaming connectors

## Evaluation

The connector contract is evaluated with 44 deterministic polling and streaming cases: bounded pagination, checkpoint advancement, snapshot replay, tombstones, duplicate event coalescing, signature-before-parse ordering, cross-origin continuation rejection, and provider-specific cursors. Every documented connector is instantiated by the catalog tests. These tests validate Mari's normalized protocol; they do not benchmark upstream connector throughput.

```console
$ pytest -q tests/test_connector_contract.py tests/test_connector_events.py \
    tests/test_connector_expansion.py tests/test_priority_connectors.py \
    tests/test_remaining_connectors.py
44 passed
```

::: card
### Slack

Channels, DMs, and canonical thread documents.

```python
from mari_components.connectors import SlackConfig, poll_slack
cfg = SlackConfig(bot_token=bot_token,
    history_token=history_token, channels=("C0123",))
pages = poll_slack(cfg, request, http=http)
```
:::

::: card
### Google Drive

Drive files, Google Docs, changes, and push watches.

```python
from mari_components.connectors import GoogleDriveConfig, poll_google_drive
cfg = GoogleDriveConfig(access_token=token, folder_id="folder-id")
pages = poll_google_drive(cfg, request, http=http)
# poll_google_drive_changes(...) and start_google_drive_watch(...)
```
:::

::: card
### Confluence

Cloud pages converted from storage HTML to Markdown-like text.

```python
from mari_components.connectors import ConfluenceConfig, poll_confluence
cfg = ConfluenceConfig(site_url="https://acme.atlassian.net/wiki",
    email="bot@acme.com", api_token=token, space_key="ENG")
pages = poll_confluence(cfg, request, http=http)
```
:::

::: card
### Dropbox

Native delta cursor with explicit deleted entries.

```python
from mari_components.connectors import DropboxConfig, poll_dropbox
cfg = DropboxConfig(token=token, path="/Knowledge")
pages = poll_dropbox(cfg, request, http=http)
```
:::

::: card
### Notion

Page search and bounded block-tree ingestion.

```python
from mari_components.connectors import NotionConfig, poll_notion
cfg = NotionConfig(token=token)
pages = poll_notion(cfg, request, http=http)
```
:::

::: card
### Airtable

Base metadata and table snapshots.

```python
from mari_components.connectors import AirtableConfig, poll_airtable
cfg = AirtableConfig(token=token, base_id="appABC123")
pages = poll_airtable(cfg, request, http=http)
```
:::

::: card
### Asana

Workspace or project tasks with offset checkpoints.

```python
from mari_components.connectors import AsanaConfig, poll_asana
cfg = AsanaConfig(token=token, workspace_gid="workspace-gid",
    project_gid="project-gid")
pages = poll_asana(cfg, request, http=http)
```
:::

::: card
### Jira

Cloud issues with project or custom JQL scope.

```python
from mari_components.connectors import JiraConfig, poll_jira
cfg = JiraConfig(site_url="https://acme.atlassian.net",
    email="bot@acme.com", api_token=token, project_key="SUP")
pages = poll_jira(cfg, request, http=http)
```
:::

::: card
### Linear

Issues and comments through the GraphQL API.

```python
from mari_components.connectors import LinearConfig, poll_linear
cfg = LinearConfig(api_key=api_key, team_id="team-id")
pages = poll_linear(cfg, request, http=http)
```
:::

::: card
### Trello

Open boards, lists, and cards.

```python
from mari_components.connectors import TrelloConfig, poll_trello
cfg = TrelloConfig(api_key=api_key, token=token)
pages = poll_trello(cfg, request, http=http)
```
:::

::: card
### Zendesk

Guide articles with ordered page checkpoints.

```python
from mari_components.connectors import ZendeskConfig, poll_zendesk
cfg = ZendeskConfig(subdomain="acme",
    email="bot@acme.com", api_token=token)
pages = poll_zendesk(cfg, request, http=http)
```
:::

::: card
### GitLab

Repository documents with head cursors and resumable tree pages.

```python
from mari_components.connectors import GitLabConfig, poll_gitlab
cfg = GitLabConfig(token=token, project="acme/handbook",
    branch="main", paths=("docs/**", "README.md"))
pages = poll_gitlab(cfg, request, http=http)
```
:::

::: card
### OneDrive and SharePoint

Microsoft Graph drive deltas, downloads, and deleted items.

```python
from mari_components.connectors import MicrosoftDriveConfig, poll_microsoft_drive
cfg = MicrosoftDriveConfig(access_token=token, drive_id="drive-id",
    folder_id="root", provider="sharepoint")
pages = poll_microsoft_drive(cfg, request, http=http)
```
:::

::: card
### Box

Folder files with marker pagination.

```python
from mari_components.connectors import BoxConfig, poll_box
cfg = BoxConfig(access_token=token, folder_id="0")
pages = poll_box(cfg, request, http=http)
```
:::

::: card
### RSS / Atom

Bounded XML feeds with ETag and Last-Modified conditional polling.

```python
from mari_components.connectors import RSSConfig, poll_rss
cfg = RSSConfig(feed_url="https://example.com/feed.xml")
pages = poll_rss(cfg, request, http=http)
```
:::

::: card
### S3, GCS, and Azure Blob

SDK-neutral object listing and reading.

```python
from mari_components.connectors import ObjectStoreConfig, poll_object_store
cfg = ObjectStoreConfig(provider="s3", container="knowledge", prefix="docs/")
pages = poll_object_store(cfg, request,
    list_objects=s3_adapter.list_objects, read_object=s3_adapter.read_object)
```
:::

::: card
### Singer / Meltano

Singer RECORD and STATE messages from external taps.

```python
from mari_components.connectors import singer_pages
pages = singer_pages(tap_stdout, document=normalize_record, page_size=100)
```
:::

::: card
### Local filesystem

Stable snapshots with content revisions and resumable bounded pages.

```python
from pathlib import Path
from mari_components.connectors import FilesystemConfig, poll_filesystem
cfg = FilesystemConfig(root=Path("knowledge"), patterns=("*.md", "*.txt"))
pages = poll_filesystem(cfg, request)
```
:::

::: card
### JSON REST collections

Same-origin pagination with an injected record-to-document mapping.

```python
from mari_components.connectors import JSONAPIConfig, poll_json_api
cfg = JSONAPIConfig(url="https://api.example.com/articles",
    records_path=("data",), next_path=("paging", "next"))
pages = poll_json_api(cfg, request, http=http, document=normalize_article)
```
:::
:::::::::::::::

```{code-block} python
:caption: connector.py

from mari_components import PollRequest
from mari_components.connectors import GitHubConfig, poll_github, validate_github

config = GitHubConfig(token=token, repository="acme/product",
    paths=("docs/**",), content_types=("files", "issues"))
validation = validate_github(config, http=http)
request = PollRequest(cursor=saved_cursor, page_size=100, page_limit=20)

for page in poll_github(config, request, http=http):
    consume(page)
```

## Streaming

`stream_hints` requires a verifier, rejects oversized deliveries and batches, parses provider-specific hints, and coalesces repeated aggregate keys. It has no cursor or checkpoint. The application owns the webhook server, queue, acknowledgement, retries, and optional canonical hydration.

```{code-block} python
:caption: stream.py

from mari_components.connectors import StreamEvent, stream_hints

event = StreamEvent(provider="slack", raw_body=raw_body, headers=headers)

for hint in stream_hints((event,), verify=verify_signature):
    enqueue_canonical_refetch(hint)
```

## Connector-specific capabilities

- Eighteen catalog connectors: batch polling, validation, pagination limits, and normalized documents.
- GitHub, GitLab, Slack, Google Drive, OneDrive, SharePoint, Confluence, and Box: verified, checkpoint-free streaming hints.
- S3, GCS, and Azure Blob: injected SDK batch operations plus checkpoint-free provider-event parsing.
- CloudEvents: verified generic dirty hints with no checkpoint state.
- Singer/Meltano: bounded RECORD pages and surfaced STATE checkpoints without subprocess ownership.
- Local filesystem: content-hashed snapshots with change detection across resumed batches.
- JSON REST: bounded same-origin pages with application-defined document normalization.
- Slack: canonical thread fetch by ID.
- Google Drive: native Changes polling and push-watch registration.
- Confluence: direct canonical page fetch.
- `ConnectorDefinition.supports(ConnectorMode.POLL | STREAM)` exposes mode capabilities for setup UIs.

::: source-block
**Standards and protocol basis**

[OpenAPI: HTTP operation contracts](https://spec.openapis.org/oas/latest.html){.paper}[CloudEvents: event envelopes](https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md){.paper}[RFC 2104: HMAC verification](https://www.rfc-editor.org/rfc/rfc2104){.paper}

**Permissive implementation references** [LlamaIndex connectors — MIT](https://github.com/run-llama/llama_index){.paper} [dlt filesystem/REST sources — Apache-2.0](https://github.com/dlt-hub/dlt){.paper} [Meltano Singer SDK — Apache-2.0](https://github.com/meltano/sdk){.paper} [Unstructured ingestion — Apache-2.0](https://github.com/Unstructured-IO/unstructured){.paper}

[Provider pagination, cursor, and signature schemes differ. Mari normalizes their observable results; it does not claim a universal delivery guarantee.]{.small}
:::


Every catalog connector defines a frozen configuration object, validation, and batch polling. GitHub, GitLab, Slack, Google Drive, OneDrive, SharePoint, Confluence, and Box also accept verified provider events. S3, GCS, and Azure Blob use an SDK-neutral batch boundary and checkpoint-free event hints. Generic CloudEvents provide the streaming escape hatch. Network calls use an injected `HttpTransport`.

## How it works

A batch connector starts from the caller's cursor, requests bounded pages, normalizes provider objects, emits explicit tombstones, and returns the next cursor/checkpoint. A streaming connector verifies the raw delivery before parsing it, reduces provider payloads to bounded `ChangeHint` keys, and coalesces duplicates. Streaming has no checkpoint state. The application may canonically refetch the changed object into a `PollPage`, so partial webhook payloads cannot bypass synchronization invariants.

| Code and work | Documents and files | Business systems | Open protocols |
|---|---|---|---|
| GitHub, GitLab, Linear, Jira | Drive, OneDrive, SharePoint, Dropbox, Box, Confluence, Notion | Slack, Airtable, Asana, Trello, Zendesk | Filesystem, JSON REST, RSS/Atom, Singer, CloudEvents, S3/GCS/Azure object stores |

::::::{container} diagram flow
<div>

**Scheduled poll**[PollRequest · cursor · checkpoint]{.small}

</div>

*→*

<div>

**Canonical PollPage**[upserts · tombstones · revision]{.small}

</div>

*→*

<div>

**plan_sync**[one persistence path]{.small}

</div>
::::::

::::::{container} diagram flow
<div>

**Provider stream**[raw body · headers]{.small}

</div>

*verify + parse*

<div>

**ChangeHint**[bounded · coalesced]{.small}

</div>

*canonical refetch*

<div>

**PollPage**[same synchronization path]{.small}

</div>
::::::

## Provider examples

All polling functions accept the same `PollRequest` and injected `HttpTransport`, and return an iterator of `PollPage` values.

::::::::::::::: connector-examples
::: card
### GitHub

Files, issues, pull requests, and commits.

```python
from mari_components.connectors import GitHubConfig, poll_github
cfg = GitHubConfig(token=token, repository="acme/product",
    branch="main", paths=("docs/**",),
    content_types=("files", "issues", "pull_requests"))
pages = poll_github(cfg, request, http=http)
```
:::
