[]{#stores}[Current reference semantics]{.current-label}

# Storage protocols and conformance

## Evaluation

| Evaluation | Cases | Result | Adapter result |
|---|---:|---:|---|
| Scope, revisions, and point-in-time reads | 1 | 1 / 1 pass | In-memory reference |
| Projection replay and identity | 1 | 1 / 1 pass | In-memory reference |
| Production databases | — | Not run | Throughput and isolation unavailable |

:::{collapse} Worked compare-and-swap outcomes

| Current revision | Expected revision | Mutation result |
|---|---|---|
| None | None | Initial commit succeeds |
| `r1` | `r1` | Update to `r2` succeeds |
| `r2` | `r1` | `RevisionConflict` |
| Tenant A artifact | Tenant B scope | Not visible |
:::

### Reproduce

```console
$ pytest -q tests/test_platform.py -k 'store or projection'
```


`InMemoryArtifactStore` is the executable reference for optimistic revision checks, tenant isolation, explicit supersession, history, and point-in-time reads. Production adapters can run the same behavioral cases.

## How it works

Protocols specify observable behavior rather than backend classes. A store implementation declares capabilities, then runs a shared conformance suite against replay, atomic revision, isolation, deletion, deterministic ordering, and point-in-time cases. Cross-store operations use an application transaction/outbox boundary; Mari does not pretend separate databases share an atomic commit. Indexes remain disposable projections that can be rebuilt from documents and artifacts.

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

The bundled conformance tests cover replay safety, deterministic ordering, point-in-time reads, tenant isolation, and atomic revision checks. Physical deletion and cross-database transactions remain adapter-specific capabilities and must be tested by the host backend.
