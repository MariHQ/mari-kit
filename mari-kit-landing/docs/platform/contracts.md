[]{#contracts}[Core]{.current-label}

# Composition contracts

## Boundaries

Mari protocols describe calls at the edge of an application. Implementations
can use a local process, managed service, database, queue, or model runtime.

| Protocol | Required behavior |
|---|---|
| `PollingConnector` | Emit bounded canonical pages from a cursor or checkpoint |
| `StreamingConnector` | Verify one delivery and emit a bounded change hint |
| `DocumentStore` | Commit and resolve structurally addressed document revisions |
| `ArtifactStore` | Compare-and-swap artifact revisions, history, and point-in-time reads |
| `KnowledgeIndex` | Search with an explicit allowed-reference set |
| `Authorizer` | Decide whether one principal may read one object reference |
| `RevisionResolver` | Resolve exact material for a revision reference |
| `Serializer` | Encode and decode one declared value type |
| `Clock` | Supply an application-controlled aware timestamp |

```{code-block} python
:caption: Type-check application adapters against Mari contracts

from mari_components import Authorizer, Clock, KnowledgeIndex, RevisionRef, Serializer
from mari_components.platform import ArtifactStore, DocumentStore
from mari_components.retrieval import RevisionIndexHit

documents: DocumentStore = postgres_documents
artifacts: ArtifactStore = postgres_artifacts
index: KnowledgeIndex[str, RevisionIndexHit, RevisionRef] = opensearch_index
authorize: Authorizer[User] = company_authorizer
clock: Clock = utc_clock
serializer: Serializer[StoredArtifact] = artifact_codec
```

Runtime-checkable protocols verify method presence. Conformance functions check
behavior that structural typing cannot establish:

```{code-block} python
:caption: Check a production store adapter

from mari_components.testing import (
    assert_artifact_store_conforms,
    assert_clock_conforms,
    assert_document_store_conforms,
    assert_index_authorization_conforms,
    assert_serializer_conforms,
)

assert_document_store_conforms(make_document_store)
assert_artifact_store_conforms(make_artifact_store)
```

The same testing module supplies behavioral checks for clocks, serializers,
authorizers, and authorization-aware indexes. Callers provide representative
values, principals, references, queries, and a hit-reference accessor.

`StoreCapabilities` reports compare-and-swap, history, point-in-time reads, and
scope isolation. Applications can reject an adapter that lacks a required
capability during their own assembly step.

::: source-block
**Research and standards**

[PEP 544 structural subtyping](https://peps.python.org/pep-0544/){.paper}[W3C PROV data model](https://www.w3.org/TR/prov-dm/){.paper}

[Structural protocols preserve backend choice. Conformance cases establish the
stateful semantics that a method signature cannot express.]{.small}
:::
