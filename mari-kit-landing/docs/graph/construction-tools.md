[]{#construction-tools}[Reference]{.current-label}

# Entity and relation construction tools

## Behavior

| Stage | Mari operation | Caller responsibility |
|---|---|---|
| Blocking | Group IDs by one or more caller keys | Decide identity |
| Candidate generation | Emit unique within-block pairs | Score pairs |
| Pair scoring | Apply caller scorer and retain component evidence | Merge entities |
| Clustering | Union pairs above an explicit threshold | Persist canonical records |
| Evidence binding | Associate proposed relations with resolved evidence | Assert that relations are true |

## How it works

Blocking limits expensive pair scoring to records that share a configured key.
The reference candidate generator still examines every pair for shared keys,
so candidate enumeration has quadratic pair-check cost. Prepartition large
inputs by tenant and entity type or inject an indexed candidate generator.
Scoring stays injectable because each corpus gives its
fields different meaning. Threshold clustering returns assignments plus every
accepted link. The link set exposes transitive merges.

```{code-block} python
:caption: Compose construction primitives explicitly

from mari_components.graph import (
    explain_candidate_pairs, cluster_matches, inspect_clusters,
    resolve_relation_evidence,
)

blocked = explain_candidate_pairs(
    entity_ids=records,
    blocking_keys=lambda entity_id: (
        normalized_name[entity_id][:4],
        email_domain[entity_id],
    ),
)

clusters = cluster_matches(
    entity_ids=records,
    candidate_pairs=[(pair.left, pair.right) for pair in blocked],
    score=lambda left, right: pair_model(left, right),
    threshold=0.91,
)

diagnostics = inspect_clusters(clusters)
resolved = resolve_relation_evidence(relations, resolve=evidence_for_relation)

for cluster in clusters.clusters:
    proposals.append(application_merge_policy(cluster))
```

`BlockedPair.shared_keys` explains why comparison occurred. Cluster diagnostics
surface the weakest accepted link and any rejected pair located inside a
transitively merged cluster. `resolve_relation_evidence` omits an `accepted`
flag. Resolved evidence establishes source availability. The caller defines truth and
sufficiency policy. The older `bind_relation_evidence` compatibility function retains its
original presence-based behavior.

## Graph-to-evidence projection

`project_graph_evidence` performs a many-to-many join and retains why an
artifact was found. Every association retains the graph node, node score,
caller path, artifact revision, and evidence role. Nodes lacking evidence are
reported separately.

```{code-block} python
:caption: Project a selected graph into auditable artifacts

from mari_components.graph import project_graph_evidence

projection = project_graph_evidence(
    selected.nodes,
    artifacts=lambda node: node_artifacts.get(node, ()),
    score=node_scores.__getitem__,
    path=explanation_path,
    role=lambda node, ref: evidence_role(node, ref),
)
```

The mapping supports several nodes from one artifact. A node can resolve to several
artifacts. `artifact_refs` is a convenience deduplication. The complete
association table remains available.

Use the same scoped `ArtifactRef` values as retrieval units. Convert them through
`to_revision_ref()` when joining structural evidence or dependency stamps.
Apply authorization in the node and artifact callbacks before exposing the
projection. See [dependency-aware updates](../start/dependency-updates.md) for
rebuilding affected evidence projections after source changes.

## Version families

`resolve_version_families` groups immutable manifestations by any caller key
and proposes the highest-scored representative. Equal top scores are returned
as explicit ties. Publication and revision policy remain visible to the caller.

```{code-block} python
:caption: Group a preprint, journal article, and correction

from mari_components.knowledge import resolve_version_families

families = resolve_version_families(
    papers,
    family=lambda paper: paper.work_id,
    score=lambda paper: caller_version_priority(paper),
)

for family in families:
    if len(family.tied_representatives) > 1:
        review(family)
```

The family key and priority are application semantics. The caller chooses the
preferred manifestation among newer, published, unretracted, or canonical records.
[W3C PROV alternate and specialization relations](https://www.w3.org/TR/prov-dm/){.paper}

## Measures

| Layer | Measure |
|---|---|
| Blocking | Pair completeness and reduction ratio |
| Pair classification | Precision, recall, F1, calibration |
| Clustering | B-cubed precision/recall, pairwise F1 |
| Relations | Exact and partial relation precision/recall with evidence |
| End-to-end construction | KGCQual components and downstream task delta |

::: source-block
**Papers and implementations**

[Fellegi--Sunter record linkage](https://doi.org/10.1080/01621459.1969.10501049){.paper}[Dedupe](https://github.com/dedupeio/dedupe){.paper}[DeepMatcher](https://arxiv.org/abs/1710.00597){.paper}[BenchIE](https://arxiv.org/abs/2109.06850){.paper}

[Mari exposes deterministic blocking and threshold clustering. Feature learning and merge policy remain caller-owned.]{.small}
:::
