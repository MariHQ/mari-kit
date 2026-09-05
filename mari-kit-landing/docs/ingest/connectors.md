[]{#connectors}[Supported]{.current-label}

# Polling and streaming connectors

## Behavior

| Mode | Use it for | Delivery contract |
|---|---|---|
| Polling | Complete snapshots and cursor-based change feeds | Bounded pages. Checkpoint advances after a complete page |
| Streaming | Low-latency change notification | Verify, normalize, coalesce, then fetch canonical state. No checkpoint required |
| Singer | Existing tap ecosystems | Convert Singer records and state messages into bounded source pages |

All 18 connector definitions are exercised against recorded or synthetic provider shapes. That establishes pagination, identity, tombstone, and event-normalization behavior. Provider uptime and throughput require provider-specific measurements.

## Shared function definitions and options

| Function / value | Required inputs | Important options |
|---|---|---|
| `PollRequest` | None | `cursor`, `checkpoint`, positive `page_size`, positive `page_limit` |
| `connector_configuration_fingerprint` | Non-secret observed configuration | Binds durable sync state to the selected provider scope |
| `configured_source_id` | Provider, account identity, non-secret observed configuration | Produces a stable fingerprinted source identity |
| `poll_*` | Frozen provider config, request, injected transport | Provider selection fields and explicit content-type scope |
| `stream_change_hint` | One raw `StreamEvent`, verifier | `maximum_bytes`. Verification always precedes parsing |
| `stream_hints` | Event iterable, verifier | `maximum_events`, `maximum_bytes`. No checkpoint state |
| `coalesce_hints_ordered` | Hints and caller `order_key` | Optional explicit tie resolver. Unresolved keys are withheld |
| `hydrate_hints` | Verified hints and canonical fetch callback | Converts hints to ordinary `PollPage` values |
| `validate_hint_hydration` | Hint and hydrated pages | Optional revision-equivalence callback. No built-in ordering assumption |

Catalog providers expose matching validation functions. HTTP validation can
contact the provider to check credentials and selected resources. Network functions accept
an `HttpTransport`. Retry scheduling, credentials, queues, and SDK clients stay
outside the connector contract.

:::{collapse} Example polling and streaming traces

| Mode | Input sequence | Emitted sequence | Checkpoint |
|---|---|---|---|
| Polling | page 1 → page 2 → complete | upserts and tombstones | Advances after complete page |
| Polling | page 1 → incomplete page 2 | partial changes withheld from reconciliation | Preserved |
| Streaming | create → duplicate create → delete | coalesced dirty hints | None |
| Streaming | invalid signature → payload | nothing parsed or emitted | None |
:::


## Provider examples

Polling returns bounded `PollPage` values. HTTP providers accept an injected
`HttpTransport`. Filesystem, object-store, and Singer adapters use their own
local, SDK, or record-stream boundaries. Examples below assume a `PollRequest`
named `request` and caller-owned credentials or adapter callbacks.

::::::::::::::: connector-examples
::: card
### GitHub

Files, issues, pull requests, and commits.

```python
from mari_components.connectors import GitHubConfig, github_source_id, poll_github
cfg = GitHubConfig(token=token, repository="acme/product",
    branch="main", paths=("docs/**",),
    content_types=("files", "issues", "pull_requests"))
source_id = github_source_id(cfg)
pages = poll_github(cfg, request, http=http)
```
:::

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

`stream_hints` requires a verifier and rejects oversized deliveries. It parses
provider-specific hints, then coalesces repeated aggregate keys. Streaming
state consists of those hints. The application owns the webhook server and
queue. It also handles acknowledgement, retries, and optional canonical
hydration.

Arrival order can differ from revision order. `coalesce_hints_ordered`
accepts a caller ordering key and separately reports stale hints, exact
duplicates, and equal-order conflicts. The default withholds unresolved tied
keys from `selected`. An explicit resolver can select a tied hint.

```{code-block} python
:caption: Coalesce out-of-order changes using explicit revision keys

from mari_components.connectors import coalesce_hints_ordered

report = coalesce_hints_ordered(
    hints,
    order_key=lambda hint: revision_clock(hint.revision),
)
if report.conflicts:
    quarantine(report.conflicts)
for hint in report.selected:
    refetch(hint)
```

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
- CloudEvents: verified generic dirty hints with checkpoint-free delivery.
- Singer/Meltano: bounded RECORD pages and surfaced STATE checkpoints with subprocess ownership left to the host.
- Local filesystem: content-hashed snapshots with change detection across resumed batches.
- JSON REST: bounded same-origin pages with application-defined document normalization.
- Slack: canonical thread fetch by ID.
- Google Drive: native Changes polling and push-watch registration.
- Confluence: direct canonical page fetch.
- `ConnectorDefinition.supports(ConnectorMode.POLL | STREAM)` exposes mode capabilities for setup UIs.

::: source-block
**Standards and protocol basis**

[OpenAPI: HTTP operation contracts](https://spec.openapis.org/oas/latest.html){.paper}[CloudEvents: event envelopes](https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md){.paper}[RFC 2104: HMAC verification](https://www.rfc-editor.org/rfc/rfc2104){.paper}

**Permissive implementation references** [LlamaIndex connectors, MIT](https://github.com/run-llama/llama_index){.paper} [dlt filesystem/REST sources, Apache-2.0](https://github.com/dlt-hub/dlt){.paper} [Meltano Singer SDK, Apache-2.0](https://github.com/meltano/sdk){.paper} [Unstructured ingestion, Apache-2.0](https://github.com/Unstructured-IO/unstructured){.paper}

[Provider pagination, cursor, and signature schemes differ. Mari normalizes their observable results. Delivery guarantees remain provider-specific.]{.small}
:::


Every catalog connector defines a frozen configuration object, validation, and batch polling. GitHub, GitLab, Slack, Google Drive, OneDrive, SharePoint, Confluence, and Box also accept verified provider events. S3, GCS, and Azure Blob use an SDK-neutral batch boundary and checkpoint-free event hints. Generic CloudEvents provide the streaming escape hatch. Network calls use an injected `HttpTransport`.

## How it works

A batch connector starts from the caller's cursor and requests bounded pages.
It normalizes provider objects, emits explicit tombstones, and returns the next
cursor. A streaming connector verifies the raw delivery before parsing. It
reduces provider payloads to bounded `ChangeHint` keys and coalesces duplicates.
Each event stands on its own. The application refetches the changed object
into a canonical `PollPage`. This keeps partial webhook payloads inside sync
invariants.

`coalesce_hints_ordered` uses a caller-supplied revision ordering. It reports
older deliveries, exact duplicates, and equal-order conflicts separately. An
unresolved conflict is omitted from `selected` and its provider/aggregate key
appears in `unresolved_keys`. An explicit resolver can select a tied hint.

| Code and work | Documents and files | Business systems | Open protocols |
|---|---|---|---|
| GitHub, GitLab, Linear, Jira | Drive, OneDrive, SharePoint, Dropbox, Box, Confluence, Notion | Slack, Airtable, Asana, Trello, Zendesk | Filesystem, JSON REST, RSS/Atom, Singer, CloudEvents, S3/GCS/Azure object stores |

::::::{container} diagram flow
<div>

**Scheduled poll**[PollRequest · cursor · checkpoint]{.small}

</div>

**→**

<div>

**Canonical PollPage**[upserts · tombstones · revision]{.small}

</div>

**→**

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

Pass accepted pages through [synchronization](sync.md) before publishing
derived work. A committed source change supplies a new input snapshot for
[dependency-aware updates](../start/dependency-updates.md).
