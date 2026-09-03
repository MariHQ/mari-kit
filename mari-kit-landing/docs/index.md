[]{#overview}

::: version
mari-components · 0.1.0.dev0
:::

# Mari documentation

Mari is a framework-neutral Python library for building knowledge systems from changing source material. It supplies immutable domain types, connector contracts, synchronization planning, multi-vector, graph, and contradiction retrieval, document self-contradiction validation, rank fusion, memory update plans, topic segmentation, evidence validation, freshness tracking, workflow reuse, trajectory analysis, and verification utilities.

::: legend
Current --- implemented Proposed --- planned, not released
:::

## How to read this page

"Current" sections describe importable code in `mari_components`. "Proposed" sections describe concrete interfaces and algorithms that are not released. Each research-derived mechanism links its evidence next to the explanation; library boundaries and failure behavior are labeled as Mari engineering contracts.

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
```
