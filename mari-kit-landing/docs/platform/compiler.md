[]{#compiler}[Current]{.current-label}

# Evaluation and compilation

## Measured configuration search

| SciFact configuration search | nDCG@10 |
|---|---:|
| Selected configuration on development split | `0.639` |
| Selected configuration on held-out split | `0.683` |
| Default BM25 on the same held-out split | `0.695` |
| Held-out change | `-0.011` |

The selected configuration overfit this nine-candidate search.
`compile_configurations` records the development result and the held-out
result. Reserve held-out cases for each search. Keep the current configuration
when its held-out score remains higher.

:::{collapse} Configuration selection example

| Candidate | Grounded recall | ACL leakage | p95 latency | Decision |
|---|---:|---:|---:|---|
| A | 0.88 | 0.00 | 120 ms | Feasible |
| B | 0.92 | 0.01 | 90 ms | Rejected by ACL constraint |
| C | 0.84 | 0.00 | 70 ms | Rejected by recall minimum |

Weighted utility is computed for candidates that satisfy every constraint.
:::



`compile_configurations` searches caller-supplied pipeline and retrieval configurations against knowledge-system objectives and returns the highest-utility feasible candidate with every trial visible.

## How it works

Declare the tunable parameters and hard constraints. Add metrics used for
selection. Each candidate runs on the same frozen development cases. Mari can
cache stage results through configuration and input fingerprints. Constraint
failures remove a candidate from selection. Feasible candidates receive a
weighted utility score. Run the selected candidate once on held-out cases.
Compilation returns a report and proposal. Deployment stays in application
code.

**Research basis**[DSPy](https://arxiv.org/abs/2310.03714){.paper} compiles parameterized LM pipelines against a declared metric. Mari generalizes the search space to retrieval, indexing, parsing, graph, consolidation, and packing configuration. Hard provenance, update-fidelity, and ACL constraints are Mari requirements and must be evaluated independently.

::::::::: metric-grid
<div>

**Grounded recall**maximize

</div>

<div>

**Provenance accuracy**require 1.0

</div>

<div>

**Update fidelity**require 1.0

</div>

<div>

**ACL leakage**require 0.0

</div>

<div>

**Context tokens**minimize

</div>

<div>

**Latency p95**minimize

</div>
:::::::::

```{code-block} python
:caption: Constraint-first configuration search

from mari_components.platform import (
    MetricObjective,
    ObjectiveDirection,
    compile_configurations,
)

def evaluate(config):
    return benchmark(index=config["index"], k=config["k"])

compiled = compile_configurations(
    [
        {"index": "bm25", "k": 20},
        {"index": "hnsw", "k": 40},
    ],
    evaluate=evaluate,
    objectives=[
        MetricObjective(
            name="grounded_recall",
            direction=ObjectiveDirection.MAXIMIZE,
            minimum=0.85,
        ),
        MetricObjective(
            name="acl_leakage",
            direction=ObjectiveDirection.MINIMIZE,
            maximum=0.0,
        ),
        MetricObjective(
            name="latency_p95",
            direction=ObjectiveDirection.MINIMIZE,
            weight=0.01,
        ),
    ],
)
print(compiled.configuration, compiled.winner.metrics)
```
