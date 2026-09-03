[]{#connectors}[Current]{.current-label}

# Polling and streaming connectors

Every connector defines a frozen configuration object, validation, and polling. GitHub, Slack, Google Drive, and Confluence also accept verified provider events. Network calls use an injected `HttpTransport`.

## How it works

A polling connector starts from the caller's cursor, requests bounded pages, normalizes provider objects, emits explicit tombstones, and returns the next cursor/checkpoint. A streaming connector verifies the raw delivery before parsing it, reduces provider payloads to bounded `ChangeHint` keys, coalesces duplicates, and canonically refetches the object. Both routes produce `PollPage`, so event order, partial webhook payloads, and provider retry behavior cannot bypass synchronization invariants.

| GitHub | Slack | Google Drive | Confluence |
|---|---|---|---|
| Dropbox | Notion | Airtable | Asana |
| Jira | Linear | Trello | Zendesk |

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

`stream_pages` requires a verifier, rejects oversized deliveries and batches, parses provider-specific hints, coalesces repeated aggregate keys, and calls an injected hydration function. The application owns the webhook server, queue, acknowledgement, and retries.

```{code-block} python
:caption: stream.py

from mari_components.connectors import StreamEvent, stream_pages

event = StreamEvent(provider="slack", raw_body=raw_body, headers=headers)

def hydrate(hint):
    document, complete = fetch_slack_thread_by_id(config,
        hint.metadata["channel"], hint.metadata["thread_timestamp"], http=http)
    return (PollPage(upserts=(document,) if document else (),
        snapshot_complete=complete),)

for page in stream_pages((event,), verify=verify_signature, hydrate=hydrate):
    consume(page)
```

## Connector-specific capabilities

- All twelve connectors: polling, validation, pagination limits, normalized documents, and explicit deletion handling.
- GitHub, Slack, Google Drive, and Confluence: verified streaming change hints plus canonical refetch.
- Slack: canonical thread fetch by ID.
- Google Drive: native Changes polling and push-watch registration.
- Confluence: direct canonical page fetch.
- `ConnectorDefinition.supports(ConnectorMode.POLL | STREAM)` exposes mode capabilities for setup UIs.

::: source-block
**Standards and protocol basis**

[OpenAPI: HTTP operation contracts](https://spec.openapis.org/oas/latest.html){.paper}[CloudEvents: event envelopes](https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md){.paper}[RFC 2104: HMAC verification](https://www.rfc-editor.org/rfc/rfc2104){.paper}

[Provider pagination, cursor, and signature schemes differ. Mari normalizes their observable results; it does not claim a universal delivery guarantee.]{.small}
:::
