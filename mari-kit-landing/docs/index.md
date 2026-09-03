[]{#overview}

::: version
mari-components · 0.1.0.dev0
:::

# Mari documentation

## Evaluation

| Layer | Evaluation | Result | Detail |
|---|---|---:|---|
| Retrieval | BEIR SciFact | nDCG@10 `0.6634` | [Indexes and ranking](retrieve/retrieval.md#evaluation) |
| Long-term memory retrieval | LongMemEval-S | Recall-all@10 `0.9021` | [Memory evaluation](platform/memory-evaluation.md#evaluation) |
| API behavior | Installed repository suite | 198 / 198 pass | Each feature page lists its subset |
| Result integrity | Aggregate recomputation | 962 case records verified | `benchmarks/verify_results.py` |

| Area | What it covers |
|---|---|
| [Ingest](ingest/index.md) | Documents, polling/streaming connectors, synchronization, parsers, sections, tags |
| [Retrieve](retrieve/index.md) | Lexical, dense, multi-vector, approximate, contradiction, graph, and adaptive retrieval |
| [Govern](govern/index.md) | Evidence, contradiction validation, freshness, workflow reuse, verification, errors |
| [Memory](memory/index.md) | Admission, mutation, segmentation, salience, organization, consolidation |
| [Graphs](graph/index.md) | Resolution, temporal facts, propagation, communities, projections |
| [Agents](agents/index.md) | Trajectories, procedure mining, regression gates, reviewed reuse |
| [Platform](platform/index.md) | Artifact lineage, stores, pipelines, evaluation runs, configuration compilation |

```console
$ pytest -q
$ python benchmarks/verify_results.py
```

```{toctree}
:maxdepth: 2
:hidden:

start/index
ingest/index
retrieve/index
govern/index
memory/index
graph/index
agents/index
platform/index
```


Mari is a framework-neutral Python library for building knowledge systems from changing source material. It supplies immutable domain types, connector contracts, synchronization planning, multi-vector, graph, and contradiction retrieval, document self-contradiction validation, rank fusion, memory update plans, topic segmentation, evidence validation, freshness tracking, workflow reuse, trajectory analysis, and verification utilities.

::: legend
Current --- importable from `mari_components`
:::

## How to read this page

Each section describes importable code in `mari_components`. Research-derived mechanisms link evidence next to the explanation; application-injected model calls, persistence boundaries, and failure behavior are identified explicitly.

**Package naming**`mari-components` is the distribution. Public imports use `mari_components`.
