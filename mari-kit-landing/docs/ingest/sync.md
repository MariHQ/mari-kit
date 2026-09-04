[]{#sync}[Core]{.current-label}

# Synchronization

## Behavior

| Feed semantics | Safe deletion rule | Cursor rule |
|---|---|---|
| Full snapshot | Absence becomes deletion-eligible after the final complete page | Advance after reconciliation commits |
| Incremental feed | Delete from an explicit tombstone | Advance after every accepted complete page |
| Stream hint | Deletion follows an explicit tombstone | Streaming checkpoint field is absent |


:::{collapse} Example reconciliation differences

| Input | Previous state | Planned mutation |
|---|---|---|
| Full snapshot omits document, final page complete | Document exists | Delete |
| Full snapshot omits document, page incomplete | Document exists | No delete. Hold cursor |
| Incremental page contains tombstone | Document exists | Delete |
| Replayed incremental upsert | Same revision exists | No-op |
:::


::::::::{container} diagram state
<div>

**Start**[generation 41]{.small}

</div>

*→*

<div>

**Pages**[upsert · tombstone · unchanged]{.small}

</div>

*→*

::: gate
**Complete?**[incomplete: preserve missing docs]{.small}
:::

*→*

<div>

**Reconcile**[yes: absence is deletion-eligible]{.small}

</div>

*→*

<div>

**Commit**[CAS generation 42]{.small}

</div>
::::::::

```{code-block} python
:caption: sync.py

from mari_components import SyncMode
from mari_components.connectors import connector_configuration_fingerprint
from mari_components.sync import SyncState, plan_sync

state = load_state() or SyncState()
scope_fingerprint = connector_configuration_fingerprint({
    "repository": "acme/product",
    "branch": "main",
    "paths": ["docs/"],
})
for page in provider_pages:
    plan = plan_sync(state, page,
        source_id="github:acme/product", mode=SyncMode.FULL,
        configuration_fingerprint=scope_fingerprint)
    store.commit(upserts=plan.upserts, deletes=plan.deletes,
        state=plan.state, expected_generation=plan.expected_generation)
    state = plan.state
```

When an application exposes an atomic transaction, `apply_sync_plan` performs
the generation check, applies upserts and tombstones, and commits the proposed
state through that caller-owned protocol.

```{code-block} python
:caption: Apply a plan through application storage

from mari_components.sync import apply_sync_plan

with store.sync_transaction(source_id) as transaction:
    apply_sync_plan(plan, transaction=transaction)
```

The transaction implements `generation`, `upsert`, `delete`, and `commit`.
The host supplies the database and its transaction guarantees.
`hydrate_hints(hints, hydrate=canonical_fetch)` is the matching
bridge when verified stream hints already exist and the caller has parsed each event.

## Function definitions and options

| Function | Required inputs | Options and guarantees |
|---|---|---|
| `plan_sync` | `SyncState`, one `PollPage`, source ID, `SyncMode` | `configuration_fingerprint` binds durable state to its source selection. Full mode reconciles absence on a terminal page. Incremental mode requires tombstones |
| `stream_sync` | Page iterable and initial state | Carries an optional configuration fingerprint. Rejects an empty stream or any page after a terminal page |
| `apply_sync_plan` | Plan and caller transaction | Checks `expected_generation`. Storage atomicity remains caller-owned |
| `document_fingerprint` | `KnowledgeDocument` | Includes revision, body, ACL, timestamps, URL and metadata |
| `validate_hint_hydration` | One `ChangeHint` and hydrated pages | Optional `revision_matches` and `external_id_matches` callbacks. Reports revision, ID and deletion-shape mismatches |

The revision callback is necessary for providers whose event sequence and
canonical object revision use different encodings. Mari defaults to exact
equality and leaves revision ordering to the caller.

## Enforced invariants

- Page replay is idempotent through content fingerprints and manifests.
- Only terminal, authoritative full pages reconcile absence.
- Explicit tombstones apply in full and incremental modes.
- Incomplete full sync cannot resume as incremental.
- Generation compare-and-swap prevents concurrent state loss.
- A changed configuration fingerprint requires fresh sync state.
- Foreign source IDs, duplicate IDs, and upsert/delete overlap are rejected.

::: source-block
**Research basis**

[Build Systems à la Carte: fingerprints and minimal rebuilds](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/03/build-systems.pdf){.paper}[Dynamo: versioning and reconciliation](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf){.paper}

[Snapshot authority, deletion rules, and atomic compare-and-swap are Mari's connector/store contract.]{.small}
:::


`plan_sync` compares a durable `SyncState` with one `PollPage` and returns a side-effect-free `SyncPlan`. `stream_sync` applies the same rules across pages.

## How it works

For each upsert, Mari validates source ownership and compares a deterministic content fingerprint with the manifest. Equal fingerprints mean unchanged. Unequal fingerprints mean upsert. Explicit tombstones become deletes. Absence becomes deletion after the terminal page of an authoritative full snapshot. The returned plan carries the prior generation as a compare-and-swap precondition and the next manifest/cursor as proposed state. Persistence commits both data and state atomically.

After committing source state, construct the complete current input snapshot
for [dependency-aware updates](../start/dependency-updates.md). A sync delta
describes source mutations. A dependency plan describes the derived work
those mutations require. Keep their commits explicit so a failed derivation
remains retryable against the committed source revision.
