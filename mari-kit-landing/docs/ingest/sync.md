[]{#sync}[Current]{.current-label}

# Synchronization

## At a glance

| Feed semantics | Safe deletion rule | Cursor rule |
|---|---|---|
| Full snapshot | Absence may delete only after the final complete page | Advance after reconciliation commits |
| Incremental feed | Delete only from an explicit tombstone | Advance after every accepted complete page |
| Stream hint | Never infer deletion from silence | No streaming checkpoint required |


:::{collapse} Worked reconciliation differences

| Input | Previous state | Planned mutation |
|---|---|---|
| Full snapshot omits document, final page complete | Document exists | Delete |
| Full snapshot omits document, page incomplete | Document exists | No delete; hold cursor |
| Incremental page contains tombstone | Document exists | Delete |
| Replayed incremental upsert | Same revision exists | No-op |
:::


*→*

<div>

**Reconcile**[yes: absence may delete]{.small}

</div>

*→*

<div>

**Commit**[CAS generation 42]{.small}

</div>
::::::::

```{code-block} python
:caption: sync.py

from mari_components import SyncMode
from mari_components.sync import SyncState, plan_sync

state = load_state() or SyncState()
for page in provider_pages:
    plan = plan_sync(state, page,
        source_id="github:acme/product", mode=SyncMode.FULL)
    store.commit(upserts=plan.upserts, deletes=plan.deletes,
        state=plan.state, expected_generation=plan.expected_generation)
    state = plan.state
```

## Enforced invariants

- Page replay is idempotent through content fingerprints and manifests.
- Only terminal, authoritative full pages reconcile absence.
- Explicit tombstones apply in full and incremental modes.
- Incomplete full sync cannot resume as incremental.
- Generation compare-and-swap prevents concurrent state loss.
- Foreign source IDs, duplicate IDs, and upsert/delete overlap are rejected.

::: source-block
**Research basis**

[Build Systems à la Carte: fingerprints and minimal rebuilds](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/03/build-systems.pdf){.paper}[Dynamo: versioning and reconciliation](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf){.paper}

[Snapshot authority, deletion rules, and atomic compare-and-swap are Mari's connector/store contract.]{.small}
:::


`plan_sync` compares a durable `SyncState` with one `PollPage` and returns a side-effect-free `SyncPlan`. `stream_sync` applies the same rules across pages.

## How it works

For each upsert, Mari validates source ownership and compares a deterministic content fingerprint with the manifest: equal means unchanged; unequal means upsert. Explicit tombstones always become deletes. Absence becomes deletion only after the terminal page of an authoritative full snapshot. The returned plan carries the prior generation as a compare-and-swap precondition and the next manifest/cursor as proposed state; persistence must atomically commit both data and state.

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
**Complete?**[no: preserve missing docs]{.small}
:::
