[]{#architecture}

# Architecture

## Ownership

Mari provides composable values and algorithms. The host application decides
which computations to run, which users can access material, and when to commit.

| Mari supplies | Application supplies |
|---|---|
| Immutable source, reference, evidence, and artifact values | Source credentials and identity mapping |
| Parsing, ranking, graph algorithms, and update plans | Models, embeddings, and domain semantics |
| Connector and storage protocols | HTTP transport, databases, and transactions |
| Reference adapters and conformance checks | Scheduling, retries, capacity, and deployment |
| Validation reports and reviewable proposals | Authorization, approval, and truth policy |

## Shared contracts

The same source material can support lexical search, embeddings, exact evidence,
and derived knowledge. Keep its identity intact across these boundaries.

| Value | Role | Consumers |
|---|---|---|
| `ScopeRef` | Tenant and space partition | Source references and artifact stores |
| `ObjectRef` | Stable object within a namespace and scope | Documents, records, and derived objects |
| `RevisionRef` | Exact revision and optional unit | Evidence, structural retrieval, and freshness |
| `SemanticAtom` | Text occurrence with source coordinates | Passage retrieval, embeddings, and evidence |
| `DependencyStamp` | Current fingerprint of one input aspect | Shared update planner |
| `DerivationSpec` | Ordered inputs plus versioned computation recipe | Rebuild and reuse decisions |
| `MaterializationReceipt` | Completed output and the inputs consumed | Downstream availability and reuse |

`KnowledgeDocument.document_id` encodes source and external IDs. Add an explicit
scope when constructing a structural reference. Document IDs and graph node IDs
alone carry application-defined isolation rules.

```{code-block} python
:caption: Reuse one atom for retrieval and exact evidence

from mari_components import ObjectRef, ScopeRef
from mari_components.documents import atom_dependencies, parse_markdown, semantic_atoms
from mari_components.retrieval import RetrievalUnit

source = ObjectRef(
    namespace="document",
    object_id="refund-policy",
    scope=ScopeRef(tenant="acme", space="support"),
)
parsed = parse_markdown(
    "# Refunds\n\nRefunds close after 30 days.",
    artifact_id=source.object_id,
    revision="r1",
)
atoms = semantic_atoms(parsed.values[0])
atom = atoms[0]
unit = RetrievalUnit.from_atom(atom, source=source)
evidence = atom.located_evidence(source=source)
inputs = atom_dependencies(atom, source=source)
assert unit.ref.to_revision_ref() == evidence.ref
```

The evidence resolver returns the full source document at `r1`, since atom
character spans use document-global coordinates. The atom's text representation
can remain reusable when a source edit changes its evidence binding.

## Change propagation

```text
source revision → atoms and collection membership → representations
                         │                               │
                         └──── evidence bindings ────────┤
                                                        ↓
                                            artifacts and projections
```

Declare each computation's consumed aspects. The planner returns reusable,
ready, waiting, or blocked outputs. The host executes ready work and atomically
stores the output with its receipt, conditional on the input snapshot remaining
current. Replanning releases dependent work. Equal output fingerprints can stop
propagation after recomputation.

The [dependency-update guide](dependency-updates.md) covers collection changes,
recipe versions, failure handling, and compatibility with specialized refresh
APIs. Source availability and authorization remain explicit host inputs.

## Integration boundaries

Start with [company search](company-search.md), then add
[governed knowledge](governed-knowledge.md) or
[conversation knowledge](../agents/conversation-knowledge.md). Replace reference
stores through the [storage contracts](../platform/stores.md) and retain their
conformance checks.

Graph tools accept caller-owned IDs and callbacks. Applications define edge
semantics, traversal visibility, merge policy, and persistence. Provenance edges
record support or derivation. Computational dependencies also include selection
rules, model versions, configuration, and other inputs a citation may omit.
