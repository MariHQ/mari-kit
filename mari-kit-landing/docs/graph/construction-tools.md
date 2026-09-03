[]{#construction-tools}[Current]{.current-label}

# Entity and relation construction tools

## At a glance

| Stage | Mari operation | Does not do |
|---|---|---|
| Blocking | Group IDs by one or more caller keys | Decide identity |
| Candidate generation | Emit unique within-block pairs | Score pairs |
| Pair scoring | Apply caller scorer and retain component evidence | Merge entities |
| Clustering | Union pairs above an explicit threshold | Persist canonical records |
| Evidence binding | Associate proposed relations with resolved evidence | Assert that relations are true |

## How it works

Blocking reduces an all-pairs comparison from quadratic work to candidate pairs likely to match. Scoring stays injectable because names, addresses, identifiers, embeddings, and domain rules behave differently across corpora. Threshold clustering returns assignments plus every accepted link, making transitive merges visible.

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
transitively merged cluster. `resolve_relation_evidence` deliberately does not
contain an `accepted` flag: evidence presence is not a truth or sufficiency
policy. The older `bind_relation_evidence` compatibility function retains its
original presence-based behavior.

## What to evaluate

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
