[]{#stores}[Current reference semantics]{.current-label}

# Storage protocols

## Required semantics

| Required semantic | Why it matters |
|---|---|
| Compare-and-swap revision | Prevent stale writers from silently winning |
| Tenant-scoped reads | Keep authorization inside the query boundary |
| Immutable history | Reconstruct what was known at a prior time |
| Disposable indexes | Rebuild derived state from canonical artifacts |

The included store defines reference semantics. Measure production database
adapters for throughput and verify the same behavior.


:::{collapse} Compare-and-swap examples

| Current revision | Expected revision | Mutation result |
|---|---|---|
| None | None | Initial commit succeeds |
| `r1` | `r1` | Update to `r2` succeeds |
| `r2` | `r1` | `RevisionConflict` |
| Tenant A artifact | Tenant B scope | Hidden by scope filter |
:::



`InMemoryArtifactStore` defines the reference behavior for optimistic revision
checks and tenant isolation. It also covers explicit supersession, history, and
point-in-time reads. Production adapters preserve these semantics through
their own physical schemas.

## How it works

Protocols specify behavior that callers can observe. Each implementation
declares its support for atomic revision and history. Capability fields also
cover physical deletion and point-in-time reads. Cross-store operations use an
application transaction or outbox boundary. Each database keeps its own commit
semantics. Indexes remain disposable projections built from documents and
artifacts.

**Research basis**[Invariant confluence](https://arxiv.org/abs/1402.2237){.paper}
shows that safe coordination depends on application invariants. Mari specifies
atomicity and replay through observable behavior. Isolation, time travel, and
deletion each have explicit capability fields. The protocol split is a Mari
library design.

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

`InMemoryArtifactStore` supports replay-safe writes and deterministic ordering.
It provides point-in-time reads, tenant isolation, and atomic revision checks.
Adapters declare their physical-deletion and cross-database transaction
capabilities. Check those fields before using these operations.
