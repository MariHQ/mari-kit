# Organize memory

## Memory operations


| Stage | Decision |
|---|---|
| Admission | Accept, defer, reject, or quarantine a candidate |
| Mutation | Add, update, delete, or no-op against existing memory |
| Organization | Link notes, rank salience, or produce evidence notes |
| Consolidation | Select bounded offline work by utility and cost |
| Scope promotion | Propose a broader-scope artifact linked to its origin |
| Experience | Turn observed work and expert corrections into evidence-bound knowledge proposals |

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
experience-knowledge
memory-organization
admission
scopes
consolidation
```
