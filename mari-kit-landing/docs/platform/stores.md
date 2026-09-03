[]{#stores}[Proposed]{.proposed-label}

# Storage protocols and conformance

Capability protocols would allow independent document, artifact, vector, lexical, and graph implementations.

## How it works

Protocols specify observable behavior rather than backend classes. A store implementation declares capabilities, then runs a shared conformance suite against replay, atomic revision, isolation, deletion, deterministic ordering, and point-in-time cases. Cross-store operations use an application transaction/outbox boundary; Mari does not pretend separate databases share an atomic commit. Indexes remain disposable projections that can be rebuilt from documents and artifacts.

**Research basis**[Invariant confluence](https://arxiv.org/abs/1402.2237){.paper} shows that safe coordination depends on application invariants. Mari therefore specifies atomicity, replay, isolation, time-travel, and deletion behavior independently of backend methods. The protocol split is library design, not a result asserted by the paper.

```{code-block} python
:caption: proposed / stores.py

class DocumentStore(Protocol):
    def commit_sync(self, plan: SyncPlan) -> None: ...
    def get_many(self, ids: Iterable[str]) -> Sequence[KnowledgeDocument]: ...

class ArtifactStore(Protocol):
    def apply(self, mutation: ArtifactMutation) -> None: ...
    def at_time(self, id: str, when: datetime) -> KnowledgeArtifact | None: ...

class VectorIndex(Protocol): ...
class LexicalIndex(Protocol): ...
class GraphIndex(Protocol): ...
```

Conformance tests would cover replay safety, deterministic ordering, point-in-time reads, tenant isolation, atomic revisions, and delete behavior.
