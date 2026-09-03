# Organize memory

## Evaluation

| Feature | Evaluation | Result | Detail |
|---|---|---:|---|
| [Session retrieval](memory-algorithms.md#evaluation) | LongMemEval-S | Recall-all@10 `0.9021` | 470 scored questions |
| [Mutations and segmentation](memory-algorithms.md#evaluation) | Conformance | 4 / 4 pass | F1 not measured |
| [Organization and salience](memory-organization.md#evaluation) | Conformance | 5 / 5 pass | Task uplift not measured |
| [Admission](admission.md#evaluation) | Conformance | 4 / 4 pass | Detection quality not measured |
| [Consolidation](consolidation.md#evaluation) | Conformance | 4 / 4 pass | End-to-end quality not measured |

| Stage | Decision |
|---|---|
| Admission | Accept, defer, reject, or quarantine a candidate |
| Mutation | Add, update, delete, or no-op against existing memory |
| Organization | Link notes, rank salience, or produce evidence notes |
| Consolidation | Select bounded offline work by utility and cost |

:::{collapse} Actual memory-retrieval snapshot

| LongMemEval case | Required sessions | Retrieved within top five | Recall-all@5 |
|---|---:|---:|---:|
| `e47becba` | 1 | 1 | 1.0 |
| `6d550036` | 4 | 1 | 0.0 |

Retrieving one useful session is insufficient for a question whose answer spans four sessions.
:::


```{toctree}
:maxdepth: 1

memory-algorithms
memory-organization
admission
consolidation
```
