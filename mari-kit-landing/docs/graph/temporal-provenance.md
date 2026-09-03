[]{#temporal-provenance}[Current]{.current-label}

# Temporal and provenance utilities

## At a glance

| Operation | Inputs | Output |
|---|---|---|
| Interval overlap | Two valid-time intervals | Boolean and intersection |
| Temporal join | Keyed, interval-bearing records | Pairs valid at overlapping times |
| Lineage traversal | Artifact ID and `parents(id)` | Ancestors with depth |
| Taint composition | Input artifact IDs and `taints(id)` | Stable union with source trace |

Use these operations when the application supplies the temporal and provenance semantics; Mari does not infer them.

## How it works

Temporal functions treat intervals as half-open `[start, end)`, avoiding ambiguity at adjacent boundaries. Provenance functions walk IDs through caller callbacks and do not require Mari artifacts. Cycle and visit limits make malformed lineage observable instead of hanging traversal.

```{code-block} python
:caption: Join temporal records and explain a derived result

from mari_components.graph import temporal_join, trace_lineage_edges
from mari_components.knowledge import Assertion, valid_at

pairs = temporal_join(
    prices,
    contracts,
    left_key=lambda price: price.product_id,
    right_key=lambda contract: contract.product_id,
    left_interval=lambda price: price.validity,
    right_interval=lambda contract: contract.validity,
)

trace = trace_lineage_edges(
    "summary:q3",
    parents=provenance_store.parent_edges,
    max_depth=20,
)

current = valid_at(query_time, interval=lambda assertion: assertion.valid_time)
eligible_assertions = [assertion for assertion in assertions if current(assertion)]
```

`Assertion` binds caller-defined subject, predicate, and value fields to valid
time, transaction time, artifact evidence, and explicit supersession IDs.
`group_assertions` groups by caller semantics. `plan_assertion_update` only
implements mechanics after the caller selects `supersede`, `retract`,
`coexist`, or `dispute`; it does not infer which disposition is true.

Metadata-preserving lineage edges retain input role, operation, and arbitrary
parameters during traversal. Plain ID-only lineage remains available through
`trace_lineage`.

```{code-block} python
:caption: Keep evidence and temporal accuracy as separate measurements

from mari_components.evaluation import evaluate_graph_context

metrics = evaluate_graph_context(
    selected_nodes=context.nodes,
    evidence_required=gold.evidence_nodes,
    temporally_valid=valid_node_ids,
    edges=context_edges,
)

assert metrics.evidence_coverage == 1.0
print(metrics.temporal_precision)  # may still be below 1.0
```

## What to evaluate

| Property | Cases |
|---|---|
| Interval semantics | Adjacent, open-ended, contained, and zero-overlap intervals |
| Temporal join | Multiple overlaps and stable ordering |
| Provenance completeness | Every declared parent reachable in the trace |
| Cycle handling | Cycle reported once without infinite traversal |
| Taint conservation | Derived output contains the union of source taints |
| Temporal context | Report evidence coverage and temporal precision separately |

::: source-block
**Papers and standards**

[Temporal databases](https://doi.org/10.1016/0306-4379(86)90030-1){.paper}[Temporal knowledge graph survey](https://arxiv.org/abs/2201.08236){.paper}[W3C PROV](https://www.w3.org/TR/prov-overview/){.paper}[Graphiti temporal model](https://github.com/getzep/graphiti){.paper}

[These are value and traversal utilities. Mari does not mandate bitemporality or a provenance storage layout.]{.small}
:::
