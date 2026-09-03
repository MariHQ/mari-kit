# Organize memory

## Choose a memory operation


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
