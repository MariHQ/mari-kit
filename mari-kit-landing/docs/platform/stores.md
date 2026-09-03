[]{#stores}[Current reference semantics]{.current-label}

# Storage protocols

## At a glance

| Required semantic | Why it matters |
|---|---|
| Compare-and-swap revision | Prevent stale writers from silently winning |
| Tenant-scoped reads | Keep authorization inside the query boundary |
| Immutable history | Reconstruct what was known at a prior time |
| Disposable indexes | Rebuild derived state from canonical artifacts |

The included store is a reference implementation, not a production throughput claim. Database adapters should be evaluated against these semantics.


:::{collapse} Worked compare-and-swap outcomes

| Current revision | Expected revision | Mutation result |
|---|---|---|
| None | None | Initial commit succeeds |
| `r1` | `r1` | Update to `r2` succeeds |
| `r2` | `r1` | `RevisionConflict` |
| Tenant A artifact | Tenant B scope | Not visible |
:::



`InMemoryArtifactStore` defines the reference behavior for optimistic revision checks, tenant isolation, explicit supersession, history, and point-in-time reads. Production adapters should preserve those semantics even when their physical schemas differ.

## How it works

Protocols specify observable behavior rather than backend classes. An implementation declares whether it supports atomic revision, history, physical deletion, and point-in-time reads. Cross-store operations use an application transaction or outbox boundary; Mari does not pretend separate databases share an atomic commit. Indexes remain disposable projections that can be rebuilt from documents and artifacts.

**Research basis**[Invariant confluence](https://arxiv.org/abs/1402.2237){.paper} shows that safe coordination depends on application invariants. Mari therefore specifies atomicity, replay, isolation, time-travel, and deletion behavior independently of backend methods. The protocol split is library design, not a result asserted by the paper.

```{code-block} python
:caption: Compare-and-swap revisions with explicit lineage

from mari_components.platform import InMemoryArtifactStore, RevisionConflict

store = InMemoryArtifactStore()
store.commit(first_revision, expected_revision=None)

try:
    store.commit(second_revision, expected_revision="stale-revision")
except RevisionConflict:
    refresh_and_retry()

current = store.get("fact:refund-window", scope=scope)
historical = store.at_time(
    "fact:refund-window",
    scope=scope,
    known_at=query_time,
)
```

`InMemoryArtifactStore` supports replay-safe writes, deterministic ordering, point-in-time reads, tenant isolation, and atomic revision checks. Physical deletion and cross-database transactions remain adapter-specific capabilities; check a backend's declared capabilities before relying on them.
