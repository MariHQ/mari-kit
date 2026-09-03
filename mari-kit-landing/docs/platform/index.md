# Platform

## Evaluation

| Feature | Evaluation | Result | Detail |
|---|---|---:|---|
| [Artifacts](artifacts.md#evaluation) | 8 deterministic cases | 8 / 8 pass | Interchange not measured |
| [Stores](stores.md#evaluation) | 2 deterministic cases | 2 / 2 pass | Production adapters not measured |
| [Pipelines](pipelines.md#evaluation) | 1 deterministic case | 1 / 1 pass | Throughput not measured |
| [Memory evaluation](memory-evaluation.md#evaluation) | LongMemEval-S | Recall-all@10 `0.9021` | End-to-end QA not measured |
| [Compiler](compiler.md#evaluation) | 1 deterministic case | 1 / 1 pass | Held-out uplift not measured |

| Platform object | Responsibility |
|---|---|
| `KnowledgeArtifact[T]` | Shared identity, scope, lineage, review, and time |
| Store protocol | Observable revision, isolation, history, and read semantics |
| `Pipeline` and `Stage` | Deterministic transforms and complete traces |
| `EvaluationRun` | Pinned corpus, configuration, model, and metrics |
| `compile_configurations` | Constraint-first selection among evaluated configurations |

:::{collapse} Worked artifact flow

| Operation | Observable record |
|---|---|
| Parse source revision | Artifact with `derived_from` lineage |
| Commit with expected revision | New immutable revision or `RevisionConflict` |
| Replay source events | Projection with content-derived build ID |
| Evaluate configuration | Trial metrics, constraint failures, selected candidate |
:::


```{toctree}
:maxdepth: 1

artifacts
stores
pipelines
memory-evaluation
compiler
```
