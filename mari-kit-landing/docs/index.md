[]{#overview}

::: version
mari-components · 0.1.0.dev0
:::

# Mari documentation

## Evaluation

Evaluation is documented beside each feature rather than in a separate catalog. The current public-corpus measurements are attached to [retrieval](retrieve/retrieval.md#evaluation) and [long-horizon memory](platform/memory-evaluation.md#evaluation). Every other research-derived page identifies its executable conformance cases and explicitly names the corpus results that remain unmeasured. The documentation audit fails if a cited page lacks an evaluation section.

```console
$ pytest -q
196 passed
$ python benchmarks/verify_results.py
verified 3 reports and 962 case records
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
