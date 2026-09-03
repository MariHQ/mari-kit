[]{#graph-diff-quality}[Current]{.current-label}

# Graph comparison and quality diagnostics

## Behavior

| Input condition | Diagnostic | Interpretation left to caller |
|---|---|---|
| Edge references absent node | Dangling edge | Reject, repair, or allow external identity |
| Node has degree zero | Orphan | Valid isolated fact or missing relation |
| Several nodes share a fingerprint | Duplicate group | Alias, duplicate, or intentional version |
| Revision changes edges | Structural diff | Expected update or unexpected drift |

## How it works

`graph_diff` compares caller-provided node IDs and hashable edge keys.
`inspect_graph_quality` calculates structural observations. The caller sets
thresholds and acceptance policy.

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

The diff uses exact identity and set semantics. Callers can run entity
resolution before comparison when that is appropriate.

`diff_records` detects changes that preserve node identity, such as a modified
function body or an updated entity attribute. Identity and fingerprints remain
caller projections.

```{code-block} python
:caption: Separate structural and attribute changes

from mari_components.graph import diff_records

records = diff_records(
    previous.symbols,
    current.symbols,
    identity=lambda symbol: symbol.qualified_name,
    fingerprint=lambda symbol: (symbol.signature, symbol.body_hash),
)

for change in records.modified:
    schedule_impact_analysis(change.record_id)
```

When a fingerprint says that a record changed, `diff_record_fields` can name
the caller-projected fields responsible for the change.

```{code-block} python
:caption: Explain a stable policy clause revision

from mari_components.graph import diff_record_fields

changes = diff_record_fields(
    previous.clauses,
    current.clauses,
    identity=lambda clause: clause.clause_id,
    fields={
        "text": lambda clause: clause.text,
        "scope": lambda clause: clause.scope,
        "effective": lambda clause: clause.valid_time,
    },
)
```

## Measures

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

[KGCQual is Apache-2.0. Mari's built-in report is structural and model-free. Semantic fidelity evaluators remain injectable.]{.small}
:::
