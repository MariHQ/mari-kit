[]{#graph-diff-quality}[Current]{.current-label}

# Graph comparison and quality diagnostics

## At a glance

| Input condition | Diagnostic | Interpretation left to caller |
|---|---|---|
| Edge references absent node | Dangling edge | Reject, repair, or allow external identity |
| Node has degree zero | Orphan | Valid isolated fact or missing relation |
| Several nodes share a fingerprint | Duplicate group | Alias, duplicate, or intentional version |
| Revision changes edges | Structural diff | Expected update or unexpected drift |

## How it works

`graph_diff` compares caller-provided node IDs and hashable edge keys. `inspect_graph_quality` calculates structural observations without declaring the graph good or bad. Thresholds and acceptance policy remain outside Mari.

```{code-block} python
:caption: Inspect two arbitrary graph projections

from mari_components.graph import graph_diff, inspect_graph_quality

change = graph_diff(
    before_nodes=previous.node_ids,
    before_edges=previous.edge_keys,
    after_nodes=current.node_ids,
    after_edges=current.edge_keys,
)

quality = inspect_graph_quality(
    nodes=current.node_ids,
    edges=current.endpoints,
    fingerprint=lambda node: normalized_identity[node],
)
```

The diff uses exact identity and set semantics. It does not infer that renamed nodes are equivalent; callers can run entity resolution before comparison when that is appropriate.

## What to evaluate

| Measure | Calculation |
|---|---|
| Node/edge change rate | Symmetric difference divided by union |
| Dangling-edge rate | Edges with missing endpoints divided by edges |
| Orphan rate | Zero-degree nodes divided by nodes |
| Duplicate rate | Nodes in repeated fingerprint groups divided by nodes |
| Construction fidelity | Entity completeness, relation preservation, multiplicity, negation |

::: source-block
**Papers and implementations**

[KGCQual](https://arxiv.org/abs/2607.10212){.paper}[KGCQual implementation](https://github.com/kracr/kg-quality-metric){.paper}[Structural quality metrics](https://arxiv.org/abs/2211.10011){.paper}[Knowledge graph quality survey](https://doi.org/10.1145/3360901){.paper}

[KGCQual is Apache-2.0. Mari's built-in report is structural and model-free; semantic fidelity evaluators remain injectable.]{.small}
:::
