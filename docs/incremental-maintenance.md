# Incremental knowledge maintenance

Mari's shared update contracts now cover collection selection, indexed change
propagation, stable group lineage, and reversible aggregates. These algorithms
compose with existing atoms, structural references, and materialization receipts.
The host owns models, authorization, persistence, scheduling, and transactions.

## Select collections before consuming their members

An answer about all refund discussions depends on the selection rule as well as
the discussions previously found. A new discussion can change the result even
though it has no edge in the old dependency graph.

`SelectionSpec` identifies a scoped collection and versions its rule. Pass the
complete candidate partition to `plan_selection`. Each candidate stamp must
fingerprint every field the selector reads. Additional dependency stamps cover
policy, query configuration, index versions, or external selection inputs.

```python
from mari_components import (
    SelectionSpec, UpdateAction, complete_selection, plan_selection,
)

rule = SelectionSpec(
    object=collection_ref,
    implementation="refund-discussions:v1",
    configuration={"query": "refund policy", "limit": 20, "ranker": "v2"},
)
selection = plan_selection(
    rule, all_candidate_stamps,
    dependencies=(policy_stamp,), previous=stored_selection,
)
if selection.update.action is UpdateAction.REBUILD:
    selected_keys = host_select(selection.candidates)
    receipt = complete_selection(selection, selected_keys)
    host_commit_if_snapshot_current(receipt)
```

Insertions, deletions, candidate edits, rule changes, and policy changes trigger
reevaluation. This includes nonwinners from a previous top-k selection. Semantic
selection uses conservative invalidation, with no inferred exclusion bound.
Only pass already-authorized material to model callbacks. A policy stamp tracks
change and does not grant access.

The completed selection fingerprints ordered membership. `consumer_inputs`
contains that membership stamp plus the exact selected candidate stamps. If the
selector runs again and picks the same members, its unchanged membership can
stop propagation. An edit to a selected revision still reaches its consumers.
Do not make every consumer depend directly on the whole candidate universe.

The selector itself is application code. Declare deterministic tie-breaking and
version its model, query, thresholds, limits, and configuration. A selection
receipt records completed work, not predicted winners.

When the selection derivation belongs to the same dependency graph as its
consumers, pass its completed materialization receipt to the planner. The
membership output has that derivation as its producer, so do not also supply it
as an external source. Supply the selected candidate stamps as current sources.

## Maintain an indexed dependency frontier

`DependencyIndex` caches the same decisions as `plan_dependency_updates` and
adds a reverse dependency index. Source and receipt changes reevaluate direct
dependents, propagating changes in completed fingerprints, availability, or
blocked state. `last_evaluated` exposes the work inspected by the last update.

```python
from mari_components import DependencyIndex

index = DependencyIndex(
    sources=current_sources, derivations=recipes, materializations=receipts,
)
visited = index.apply(
    sources=changed_stamps,
    removed_sources=deleted_keys,
    materializations=completed_receipts,
    evicted_outputs=evicted_keys,
)
plan = index.plan(targets=(requested_output,))
for task in plan.ready:
    host_execute_and_commit(task)
```

This delta API differs deliberately from the snapshot planner: omitted sources
are unchanged. Delete them explicitly with `removed_sources`. Evict a receipt
when its material is unavailable. Topology changes use `derivations` and
`removed_derivations`. These edits rebuild and cycle-check the index atomically.
Invalid conflicting edits leave its state intact.

Target selection returns the requested outputs and their ancestors. It limits
returned work, not background index maintenance. Retirement hints belong to the
complete index and are not caused by omitting a target.

Source/receipt updates avoid scanning unrelated derivations. Full plan rendering
still enumerates the graph. Initial construction and topology changes are full
passes. In the deterministic independent-branch test, changing one source
evaluates one of 2,000 outputs. This is a work-count check, not a latency claim.

The index is a process-local, single-writer reference implementation. Restore it
from source snapshots, derivations, and receipts. The host must atomically commit
outputs and receipts conditional on their input snapshot, and serialize access
to the in-memory index. It performs no background work or storage I/O.

## Preserve identity through regrouping

`reconcile_groups` accepts old stable groups and new candidate groups in one
explicit scope and namespace. `GroupIdentity.members` uses stable `ObjectRef`
values, rather than revision IDs, so content edits can retain membership identity.

```python
from mari_components import reconcile_groups

lineage = reconcile_groups(
    old_groups, new_candidate_groups,
    scope=scope, namespace="topic", generation=transaction_id,
)
for assignment in lineage.assignments:
    host_record(assignment.group, assignment.predecessors, assignment.transitions)
```

Matching uses positive exact overlap, ordered by Jaccard similarity,
intersection count, old identity, and candidate member keys. Greedy one-to-one
assignment allows one split child to retain an old identity and one predecessor
to survive a merge. All overlapping predecessors remain in the lineage report.
Transitions identify creation, continuation, splitting, and merging. Unmatched
old identities are retired hints, not deletion commands.

Supply a unique, persisted generation token for each regrouping transaction.
Use the same token when retrying that transaction. New IDs include this token
and membership so retired groups are not accidentally resurrected.

This is a deterministic overlap heuristic, not maximum-weight matching or a
semantic truth judgment. Membership changes still invalidate computations under
the retained identity. Similarity-based clustering can propose candidate groups
upstream, but cannot establish byte equality or safe reuse.

## Update reversible aggregates from keyed contributions

`DeltaReducer` defines pure `zero`, signed `change`, and `finish` operations.
`DeltaAggregate` retains immutable per-key contributions and applies additions,
replacement, and removal. Replayed identical upserts and repeated deletions are
idempotent. Invalid batches leave the aggregate unchanged.

| Reducer | Contribution | Output |
|---|---|---|
| `CountReducer` | Any JSON value per key | Active contribution count |
| `WeightedVectorReducer` | Vector and positive weight | Weighted sums, total weight, count, centroid |
| `LexicalStatisticsReducer` | Term-frequency map per document | Corpus frequency, document frequency, total length, document count |
| `MembershipReducer` | Unique target strings per source | Target reference counts, with source targets retained in contributions |

```python
from mari_components import DeltaAggregate, WeightedVectorReducer

aggregate = DeltaAggregate(WeightedVectorReducer(), scope=scope)
aggregate.apply(((atom_key, {"vector": [0.1, 0.2], "weight": 2}),))
aggregate.apply(removed=(deleted_atom_key,))
centroid = aggregate.value["centroid"]
output_stamp = aggregate.stamp(centroid_output_key)
```

Numeric accumulation uses exact rational arithmetic with a final float
conversion. This avoids edit-order drift at reference-implementation cost.
Numbers are interpreted through their decimal string representation. Immutable
counter snapshots copy their mappings, so delta arithmetic does not imply
constant-time snapshot creation or serialization.
Reject nonfinite numbers and inconsistent dimensions. A new embedding space
requires a new recipe and rebuilding its vector aggregate.

Lexical updates maintain statistics, not a complete incremental BM25 search
engine. Membership target strings require host-defined scoped encoding.
Custom reducers must preserve prior state and implement valid reversible
operations. Generated summaries are not additive aggregates: rebuild them from
declared inputs and compare actual output fingerprints.

## Complete conversation maintenance example

Run `python -m examples.quickstarts.knowledge_maintenance` from the installed
repository. The fixture host connects:

```text
current messages and access policy
  → collection selection
  → stable episodes and evidence-bound extraction
  → stable topics, membership, and topic briefs
  → separate summary text and vector derivations
  → current retrieval projection and aggregate statistics
```

All derivations use the same planner contracts. One edited message rebuilds one
topic vector. A revision-only edit updates evidence but reuses unchanged text
vectors. Topic splits and merges preserve explicit lineage. The example resolves
source evidence again before serving search results and withholds a projection
whose upstream build failed.

After each event, the example compares outputs and receipts with clean execution
of the same graph and assigned identities. Tests cover insertions, deletions,
empty collections, access changes, extraction and embedding recipes, regrouping,
failure/retry, randomized planner deltas, and reversible aggregate updates.
Grouping policy and model outputs are deterministic fixtures. These checks do
not establish semantic extraction quality or production performance.

The older conversation and topic compilers retain their compatibility APIs.
This example composes the new common contracts around episode parsing rather
than silently replacing their caches. Existing atom stamps can enter exactly
the same derivations and reducers.
