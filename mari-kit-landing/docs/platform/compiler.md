[]{#compiler}[Current]{.current-label}

# Evaluation and compilation

## Evaluation

| Evaluation | Cases | Result | Task result |
|---|---:|---:|---|
| Constraint filtering and utility selection | 1 | 1 / 1 pass | — |
| DSPy-style held-out optimization | — | Not run | Quality uplift unavailable |

:::{collapse} Worked configuration selection

| Candidate | Grounded recall | ACL leakage | p95 latency | Decision |
|---|---:|---:|---:|---|
| A | 0.88 | 0.00 | 120 ms | Feasible |
| B | 0.92 | 0.01 | 90 ms | Rejected by ACL constraint |
| C | 0.84 | 0.00 | 70 ms | Rejected by recall minimum |

Only feasible candidates reach weighted utility comparison.
:::

### Reproduce

```console
$ pytest -q tests/test_platform.py -k compiler
```


`compile_configurations` searches caller-supplied pipeline and retrieval configurations against knowledge-system objectives and returns the highest-utility feasible candidate with every trial visible.

## How it works

Declare tunable parameters, hard constraints, and optimization metrics. For each candidate configuration, run the same frozen training cases, cache stage results by configuration/input fingerprints, reject any candidate that violates provenance, update fidelity, or ACL constraints, and rank feasible candidates on grounded recall, cost, and latency. Validate the selected configuration once on held-out cases; compilation returns a report and proposal, never a deployment side effect.

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
