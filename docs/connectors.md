# Polling and streaming connectors

Mari exposes two ingestion contracts. Both end at `PollPage`, so replay-safe
synchronization, tombstones, revisions, ACL metadata, and checkpoint handling
do not depend on how a change was discovered.

```text
scheduled poll ─ PollRequest ─ poll_* ───────────────┐
                                                     ├─ PollPage ─ plan_sync
provider event ─ verify ─ ChangeHint ─ refetch ──────┘
```

## Polling

Every catalog connector supports `ConnectorMode.POLL`. A polling connector
accepts its frozen provider configuration, a `PollRequest`, and an injected
`HttpTransport`; it yields canonical `PollPage` values.

```python
from mari_components import PollRequest
from mari_components.connectors import GitHubConfig, poll_github

request = PollRequest(
    cursor=state.cursor,
    checkpoint=state.checkpoint,
    page_size=100,
    page_limit=20,
)
pages = poll_github(
    GitHubConfig(token=token, repository="acme/product"),
    request,
    http=http,
)
```

Use polling for initial snapshots, periodic repair, and providers without an
event integration. An incomplete page cannot advance the durable cursor.

## Streaming

GitHub, Slack, Google Drive, and Confluence currently advertise
`ConnectorMode.STREAM`. `StreamEvent` is the delivery boundary. The application
owns the HTTP server, queue, acknowledgement, credentials, and retry schedule.
Mari requires an injected verifier before parsing the raw body.

```python
from mari_components import PollPage
from mari_components.connectors import StreamEvent, stream_pages
from mari_components.connectors.events import verify_slack_signature

event = StreamEvent(
    provider="slack",
    raw_body=request_body,
    headers=request_headers,
)

def verify(event):
    verify_slack_signature(
        event.raw_body,
        event.headers["X-Slack-Request-Timestamp"],
        event.headers["X-Slack-Signature"],
        signing_secret,
    )

def hydrate(hint):
    document, complete = fetch_slack_thread_by_id(
        config,
        str(hint.metadata["channel"]),
        str(hint.metadata["thread_timestamp"]),
        http=http,
    )
    if document is None:
        return (PollPage(snapshot_complete=complete),)
    return (PollPage(upserts=(document,), snapshot_complete=complete),)

for page in stream_pages((event,), verify=verify, hydrate=hydrate):
    commit(plan_sync(state, page, source_id="slack", mode=SyncMode.INCREMENTAL))
```

`stream_pages` performs these operations in order:

1. Invoke `verify` for every delivery.
2. Reject oversized bodies and batches.
3. Parse a provider-specific `ChangeHint`.
4. Coalesce repeated hints for the same provider aggregate.
5. Call `hydrate` to fetch canonical provider state.
6. Yield ordinary pages to the existing synchronization path.

Event payloads are dirty notifications, not source documents. This prevents a
partial webhook body from replacing a complete Slack thread, Confluence page,
Drive file, or repository view.

## Capability discovery

```python
from mari_components.connectors import ConnectorMode, connector_definitions

polling = [row.key for row in connector_definitions() if row.supports(ConnectorMode.POLL)]
streaming = [row.key for row in connector_definitions() if row.supports(ConnectorMode.STREAM)]
```

Downstream connectors can use `PollingConnector` and `StreamingConnector` for
typing and `check_connector_contract` or
`check_streaming_connector_contract` for deterministic fixture tests.
