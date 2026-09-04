[]{#stores}[Reference]{.current-label}

# Storage protocols

## Required semantics

| Required semantic | Why it matters |
|---|---|
| Compare-and-swap revision | Prevent stale writers from silently winning |
| Tenant-and-space-scoped reads | Keep stored revisions inside their isolation boundary |
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



`DocumentStore` and `ArtifactStore` specify observable behavior.
`InMemoryDocumentStore` and `InMemoryArtifactStore` implement the reference
semantics. Store keys include tenant, space, and structural object identity.
Artifact history supports point-in-time reads by `recorded_at`, independent of
commit order.

## How it works

Protocols specify behavior that callers can observe. Each implementation
declares compare-and-swap, history, point-in-time reads, and scope isolation
through `StoreCapabilities`. Cross-store operations use an
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
from mari_components.testing import assert_artifact_store_conforms

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

# Run this same suite against a production adapter factory.
assert_artifact_store_conforms(InMemoryArtifactStore)
```

`InMemoryArtifactStore` supports replay-safe writes and deterministic ordering.
It provides point-in-time reads, tenant-and-space isolation, and atomic revision
checks. `assert_document_store_conforms` and `assert_artifact_store_conforms`
exercise the public adapter contract.
