[]{#overview}

::: version
mari-components · 0.1.0.dev0
:::

# Mari documentation

## Browse by area


| Area | What it covers |
|---|---|
| [Ingest](ingest/index.md) | Documents, multimodal regions, code structure, polling/streaming connectors, synchronization, parsers |
| [Retrieve](retrieve/index.md) | Lexical, dense, multi-vector, approximate, contradiction, graph, adaptive, and lifecycle retrieval |
| [Govern](govern/index.md) | Evidence, trust-gated writes, source conflicts, retention, freshness, verification |
| [Memory](memory/index.md) | Admission, mutation, scopes, promotion, segmentation, salience, organization, consolidation |
| [Graphs](graph/index.md) | Semantic schemas, constraints, resolution, temporal facts, propagation, communities, projections |
| [Agents](agents/index.md) | Adapters and analysis for turning observed activity into knowledge evidence |
| [Platform](platform/index.md) | Portable bundles, living views, artifact lineage, stores, pipelines, task evaluation, compilation |

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


Mari is a framework-neutral Python library for knowledge from changing source
material. Its functions extract facts, validate evidence, connect records, run
retrieval, and measure results. The caller supplies graph semantics, storage,
models, and execution order. Each operation accepts caller-owned values and
returns immutable data that the caller can inspect.

::: legend
Current: importable from `mari_components`
:::

## How to use these docs

Each feature page describes importable code in `mari_components`. Sources sit
beside the mechanism they support. Code samples mark calls supplied by the
application. They also show where data crosses a persistence boundary and how
failures appear.

**Package naming**`mari-components` is the distribution. Public imports use `mari_components`.
