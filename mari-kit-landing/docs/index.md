[]{#overview}

::: version
mari-components · 0.1.0.dev0
:::

# Mari documentation

## Choose a system boundary


| Area | What it covers |
|---|---|
| [Ingest](ingest/index.md) | Documents, multimodal regions, code structure, polling/streaming connectors, synchronization, parsers |
| [Retrieve](retrieve/index.md) | Lexical, dense, multi-vector, approximate, contradiction, graph, adaptive, and lifecycle retrieval |
| [Govern](govern/index.md) | Evidence, trust-gated writes, source conflicts, retention, freshness, verification |
| [Memory](memory/index.md) | Admission, mutation, scopes, promotion, segmentation, salience, organization, consolidation |
| [Graphs](graph/index.md) | Semantic schemas, constraints, resolution, temporal facts, propagation, communities, projections |
| [Agents](agents/index.md) | Trajectories, procedure mining, regression gates, reviewed reuse |
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


Mari is a framework-neutral Python library of composable tools for extracting, validating, linking, retrieving, comparing, and evaluating knowledge from changing source material. It does not prescribe a knowledge graph, ontology, storage system, construction pipeline, agent framework, or model. Operations accept caller-owned values and return immutable candidates, scores, plans, reports, and traces.

::: legend
Current --- importable from `mari_components`
:::

## How to use these docs

Each feature page describes importable code in `mari_components`. Research-derived mechanisms link evidence next to the explanation; application-injected model calls, persistence boundaries, and failure behavior are identified explicitly.

**Package naming**`mari-components` is the distribution. Public imports use `mari_components`.
