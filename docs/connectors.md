# Polling and streaming connectors

Mari exposes separate batch and streaming contracts. Batch connectors yield
`PollPage` and may use cursors/checkpoints. Streaming connectors yield
`ChangeHint`; they never read, emit, or persist a checkpoint. Applications may
hydrate a hint into canonical `PollPage` values before synchronization.

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

GitHub, GitLab, Slack, Google Drive, OneDrive, SharePoint, Confluence, and Box
advertise `ConnectorMode.STREAM`. S3, GCS, Azure Blob, and generic CloudEvents
are also accepted without being tied to a catalog credential form. `StreamEvent` is the delivery
boundary. The application owns the HTTP server, queue, acknowledgement,
credentials, and retry schedule. Mari requires an injected verifier before
parsing the raw body.

```python
from mari_components.connectors import StreamEvent, stream_hints
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

for hint in stream_hints((event,), verify=verify):
    enqueue_canonical_refetch(hint)
```

`stream_hints` performs these operations in order:

1. Invoke `verify` for every delivery.
2. Reject oversized bodies and batches.
3. Parse a provider-specific `ChangeHint`.
4. Coalesce repeated hints for the same provider aggregate.
5. Yield the hint without creating checkpoint state.

`stream_pages` is the convenience form that additionally calls an injected
`hydrate` function and yields ordinary pages to the synchronization path.

Event payloads are dirty notifications, not source documents. This prevents a
partial webhook body from replacing a complete Slack thread, Confluence page,
Drive file, or repository view.

## Ecosystem bridges

`poll_filesystem` reads a stable, bounded local snapshot. `poll_object_store`
accepts injected list/read functions from any S3, GCS, Azure Blob, or compatible
SDK. `poll_json_api` maps same-origin paginated JSON collections through an
injected document function. `singer_pages` consumes Singer JSON messages,
making Meltano taps usable without making Mari launch subprocesses or own tap
state.

```python
from mari_components.connectors import ObjectStoreConfig, poll_object_store

pages = poll_object_store(
    ObjectStoreConfig(provider="s3", container="knowledge", prefix="docs/"),
    request,
    list_objects=s3_adapter.list_objects,
    read_object=s3_adapter.read_object,
)
```

## Capability discovery

```python
from mari_components.connectors import ConnectorMode, connector_definitions

polling = [row.key for row in connector_definitions() if row.supports(ConnectorMode.POLL)]
streaming = [row.key for row in connector_definitions() if row.supports(ConnectorMode.STREAM)]
```

Downstream connectors can use `PollingConnector` and `StreamingConnector` for
typing and `check_connector_contract` or
`check_streaming_connector_contract` for deterministic fixture tests.
