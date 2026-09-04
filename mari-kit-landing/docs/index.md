[]{#overview}

::: version
mari-components · 0.1.0.dev0
:::

# Mari documentation

Mari Kit supplies backend-agnostic values, contracts, algorithms, plans, and
conformance checks for knowledge built from changing company sources. The host
application owns its databases, model calls, authorization policy, scheduler,
graph semantics, and product behavior.

## Start with an outcome

| Build path | Result |
|---|---|
| [Company search](start/company-search.md) | Store revisions, filter authorized candidates, retrieve current evidence |
| [Governed knowledge](start/governed-knowledge.md) | Resolve typed evidence and commit reviewable derived knowledge |
| [Agent knowledge](start/agent-knowledge.md) | Convert completed activity into validated knowledge proposals |

Each path is a complete executable composition. The feature pages explain the
individual tools and the choices available when an application needs a
different implementation.

## Browse tools by area


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


:::{admonition} Maturity labels
:class: note

**Core** marks stable cross-system contracts. **Supported** marks APIs intended
for application use. **Reference** marks local correctness-oriented
implementations. **Experimental** and **Research** mark surfaces that may change.
**Proposed** marks designs awaiting a supported implementation. See
[Maturity](start/maturity.md).
:::

## How to use these docs

Each feature page describes importable code in `mari_components`. Sources sit
beside the mechanism they support. Code samples mark calls supplied by the
application. They also show where data crosses a persistence boundary and how
failures appear.

**Package naming:** Mari Kit is the project. `mari-components` is the Python
distribution. Public imports use `mari_components`.
