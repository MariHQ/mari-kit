# Platform

## Components


| Platform object | Responsibility |
|---|---|
| `KnowledgeArtifact[T]` | Shared identity, scope, lineage, review, and time |
| Store protocol | Observable revision, isolation, history, and read semantics |
| `Pipeline` and `Stage` | Deterministic transforms and complete traces |
| `EvaluationRun` | Pinned corpus, configuration, model, and metrics |
| `compile_configurations` | Constraint-first selection among evaluated configurations |
| Portable bundle | Deterministic records, provenance, tombstones, manifest, and checksums |
| Materialized view | Minimal dependency-aware refresh plan |
| Task comparison | Paired success, compliance, turns, tokens, and tool calls |

:::{collapse} Artifact flow example

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
portability
living-views
stores
pipelines
memory-evaluation
compiler
```
