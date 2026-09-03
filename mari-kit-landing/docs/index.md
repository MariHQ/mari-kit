[]{#overview}

::: version
mari-components · 0.1.0.dev0
:::

# Mari documentation

```{include} _includes/eval/start.md
```

Mari is a framework-neutral Python library for building knowledge systems from changing source material. It supplies immutable domain types, connector contracts, synchronization planning, multi-vector, graph, and contradiction retrieval, document self-contradiction validation, rank fusion, memory update plans, topic segmentation, evidence validation, freshness tracking, workflow reuse, trajectory analysis, and verification utilities.

::: legend
Current --- importable from `mari_components`
:::

## How to read this page

Each section describes importable code in `mari_components`. Research-derived mechanisms link evidence next to the explanation; application-injected model calls, persistence boundaries, and failure behavior are identified explicitly.

**Package naming**`mari-components` is the distribution. Public imports use `mari_components`.

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
benchmarks/index
```
