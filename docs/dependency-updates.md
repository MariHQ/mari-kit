# Shared dependency updates

Mari uses scoped object references, semantic atoms, and dependency receipts to
connect parsing, retrieval, evidence, derived knowledge, and projections.
`mari_components.dependencies` owns the common change-propagation algorithm.
Specialized algorithms consume these values through their existing interfaces.
Applications continue to own model calls, authorization, storage, and scheduling.

## Shared material and identity

An atom is an occurrence of source material. Its `RevisionRef` identifies the
source object, revision, and atom unit within an explicit tenant/space scope.
`SemanticAtom.to_revision_ref(source=...)` requires the supplied object's ID to
match the atom's source ID. No module silently invents an isolation scope.

| Consumer | Shared handoff |
|---|---|
| Retrieval and context selection | `RetrievalUnit.from_atom(atom, source=source)` |
| Structural BM25 index | `atom.to_revision_ref(source=source)` as the index key |
| Exact evidence validation | `atom.located_evidence(source=source)` |
| Derived knowledge | `KnowledgeArtifact.derivation_spec(inputs=...)` |
| Graph lineage | `DerivationSpec.output` and `.inputs` as caller-owned graph IDs |
| Materialized views | `plan_view_refresh` delegates change decisions to the common planner |

Atom evidence uses character offsets in the **full source document**. The
material resolver must return that document at the referenced revision, even
though the reference also identifies the atom unit. Contextual retrieval text
may include headings; evidence quotes remain exact source text.

## Dependencies describe what a computation consumes

`DependencyKey` combines an existing `ObjectRef`, optional unit ID, and aspect.
`DependencyStamp` records that input's current fingerprint. These are dependency
addresses, not a replacement object/revision model.

`atom_dependencies` supplies four aspects:

| Aspect | Changes when | Typical consumers |
|---|---|---|
| `content` | Exact atom text changes | Raw embeddings, lexical features |
| `context` | Exact heading-prefixed text changes | Contextual embeddings |
| `binding` | Revision, occurrence, coordinates, order, section, or text changes | Evidence envelopes, retrieval projections |
| `revision` | Referenced source revision changes | Revision-sensitive artifacts |

Content and context keys are content-addressed within a source's namespace and
scope. Identical text can reuse a representation after movement or duplication,
while every occurrence keeps its own evidence binding. This does not enable
cross-tenant or cross-source cache sharing. The exact text supplied by these
representations is hashed, including whitespace and Unicode distinctions.
Normalized atom hashes remain alignment hints.

Use `atom_collection_stamp` for computations over a complete document, section,
or selected collection. It captures ordered membership, including empty
collections. A summary depending only on previously observed atoms would miss
an insertion. Collection stamps make that dependency explicit. If a consumer
uses adjacent atoms, table headers, or other material beyond `contextual_text`,
declare those additional inputs too.

Access-policy versions are caller-supplied stamps, for example an `access`
aspect on the source object. Retrieval projections can depend on both vector
and policy stamps. A policy change then triggers projection work without
embedding unchanged text. A policy fingerprint is never an authorization
decision: the host must still authorize each retrieval and reuse operation.

## Version computations and record completed outputs

`DerivationSpec` declares an output aspect, ordered unique inputs, an
implementation version, and immutable configuration. Include encoder versions,
prompt versions, parsing options, and any other settings that affect the output.
A collection's external selection rule belongs in the configuration or another
input stamp. Input order and membership both affect reuse.

`MaterializationReceipt` describes an output that actually exists, the input
stamps consumed, and the implementation/configuration fingerprint. Construct it
with `materialization_receipt` only after successful execution. Store it with
the output in one transaction, conditional on the input snapshot still being
current. When evicting a cached output, remove its receipt from the planner's
input as well. The planner trusts supplied receipts; it does not inspect storage.

Output fingerprints describe the material exposed by that output aspect.
Use the actual revision for a `revision` aspect and a deterministic content
digest for a content aspect. Include evidence bindings in the fingerprint if
the output includes citations. Keeping summary text separate from its evidence
envelope allows text reuse while updating its citation coordinates.

## Plan, materialize, and replan

```python
from mari_components import (
    DependencyKey, DerivationSpec, dependency_fingerprint,
    materialization_receipt, plan_dependency_updates,
)
from mari_components.documents import atom_dependencies

inputs = atom_dependencies(atom, source=source)
embedding = DerivationSpec(
    output=DependencyKey(
        object=source,
        unit_id=inputs.content.fingerprint,
        aspect="raw_vector",
    ),
    inputs=(inputs.content.dependency,),
    implementation="embed:v1",
    configuration={"model": "pinned-model-version"},
)
plan = plan_dependency_updates(
    sources=inputs.stamps,
    derivations=(embedding,),
    materializations=stored_receipts,
)
for task in plan.ready:
    vector = host_embed(atom.text)
    receipt = materialization_receipt(
        embedding, task.inputs,
        output_fingerprint=dependency_fingerprint(vector.tolist()),
    )
    host_commit_if_inputs_current(vector, receipt)
```

The planner consumes a complete snapshot for the graph being evaluated:

- `REUSE`: the completed output still matches its recipe and inputs.
- `REBUILD`: all inputs are available and work can run now.
- `WAIT`: an upstream output must be materialized before reuse can be assessed.
- `BLOCKED`: a source is unavailable, or an upstream dependency is blocked.

Dirty and blocked outputs are absent from `plan.available`. Replan after
persisting successful receipts. If a recomputation produces the same output
fingerprint, its dependents can reuse their existing materializations. This
avoids invalidating an entire chain solely because a source was edited.
An unchanged output fingerprint never makes an undeclared dependency safe.

Missing source stamps mean unavailable, not unchanged. Omitted derivations
produce `retired` hints for existing receipts. Supply the complete intended
derivation graph for the selected scope; a partial graph is not a deletion
feed. Retirement does not delete historical artifacts or source material.
Cycles and conflicting producers are rejected. Planning uses iterative
topological traversal and supports long dependency chains.

## Compatibility and migration

Existing reference stores, parsers, rankers, and graph algorithms remain public.
Raw arrays and ranked string IDs are still useful inside numerical algorithms.
Use scoped revision references and receipts at their materialization boundaries.

`plan_atom_refresh` remains the pairwise atom convenience API and now checks exact
raw/contextual input fingerprints. Its plan assumes a fixed embedding recipe.
Use the common planner to account for model/configuration changes and downstream
consumers. `plan_view_refresh` retains its legacy delta-input contract and
expands those deltas into snapshots before invoking the common planner.
Its legacy string IDs still require the caller to isolate scopes; it cannot
express missing-source deletion. New view consumers can use scoped dependency
stamps and complete snapshots directly.

Document freshness reports and provenance review remain specialized APIs.
Their evidence and revision values can feed the common planner through
`DependencyStamp.from_revision`. Computational inputs remain explicit:
`KnowledgeArtifact.derivation_spec` does not infer an entire dependency graph
from citations or legacy string references. A citation list usually omits
selection criteria, prompts, policy, or other material used by a computation.

## Executable integration and equivalence checks

Run `python -m examples.quickstarts.dependency_updates`. The example reuses the
same atoms for retrieval units, exact evidence, governed knowledge, and graph
lineage. One paragraph edit rebuilds one raw vector. Current materializations
and their receipts match a clean rebuild.

`tests/test_dependency_updates.py` extends this to revision-only changes,
heading moves, text edits, policy changes, model changes, deletion, duplicate
atoms, and empty collections. It also tests missing inputs, failed builds,
cycles, scope separation, long graphs, and propagation stopping at unchanged
outputs. These are deterministic integration checks, not model-quality or
production-scale performance measurements. Clean-rebuild equivalence assumes
deterministic computations or replayed model outputs and complete declarations.
