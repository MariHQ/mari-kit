[]{#overview}

::: version
mari-components · 0.1.0.dev0
:::

# Mari Kit

Mari Kit supplies backend-agnostic values, contracts, algorithms, plans, and
conformance checks for knowledge built from changing company sources. The host
application owns its databases, model calls, authorization policy, scheduler,
graph semantics, and product behavior.

```{raw} html
<figure class="diagram-hero">
<svg viewBox="0 0 760 220" width="760" height="220" preserveAspectRatio="xMidYMid meet" aria-hidden="true" focusable="false" role="presentation">
  <path class="he" d="M180 110 H264"/>
  <path class="he" d="M430 110 H500 V34 H564"/>
  <path class="he" d="M430 110 H564"/>
  <path class="he" d="M430 110 H500 V186 H564"/>
  <rect class="ht" x="264" y="107" width="6" height="6"/>
  <rect class="ht" x="564" y="31" width="6" height="6"/>
  <rect class="ht ht-down" x="564" y="107" width="6" height="6"/>
  <rect class="ht" x="564" y="183" width="6" height="6"/>
  <rect class="ht" x="216" y="107" width="6" height="6"/>
  <rect class="ht" x="462" y="107" width="6" height="6"/>
  <rect class="ht" x="497" y="66" width="6" height="6"/>
  <rect class="ht" x="497" y="148" width="6" height="6"/>
  <rect class="ht" x="530" y="31" width="6" height="6"/>
  <rect class="ht ht-down" x="530" y="107" width="6" height="6"/>
  <rect class="ht" x="530" y="183" width="6" height="6"/>
  <rect class="hn" x="20.5" y="86.5" width="160" height="48"/>
  <text class="hk" x="32" y="105">source</text>
  <text class="hm" x="32" y="122">source revision</text>
  <rect class="hn" x="270.5" y="86.5" width="160" height="48"/>
  <text class="hk" x="282" y="105">units</text>
  <text class="hm" x="282" y="122">semantic atoms</text>
  <rect class="hn" x="570.5" y="12.5" width="170" height="44"/>
  <text class="hk" x="582" y="30">derived</text>
  <text class="hm" x="582" y="46">search index</text>
  <rect class="hn hn-down" x="570.5" y="88.5" width="170" height="44"/>
  <text class="hk hk-down" x="582" y="106">derived · rebuilt</text>
  <text class="hm" x="582" y="122">derived fact</text>
  <rect class="hn" x="570.5" y="164.5" width="170" height="44"/>
  <text class="hk" x="582" y="182">derived</text>
  <text class="hm" x="582" y="198">agent proposal</text>
</svg>
<figcaption>One source revision, its semantic atoms, and the derived outputs that rebuild when it changes.</figcaption>
</figure>
```

## Start with an outcome

| Build path | Result |
|---|---|
| [Company search](start/company-search.md) | Store revisions, filter authorized candidates, retrieve current evidence |
| [Governed knowledge](start/governed-knowledge.md) | Resolve typed evidence and commit reviewable derived knowledge |
| [Agent knowledge](start/agent-knowledge.md) | Convert completed activity into validated knowledge proposals |
| [Conversation knowledge](agents/conversation-knowledge.md) | Turn conversations into searchable episodes with original-message evidence |
| [Dependency-aware updates](start/dependency-updates.md) | Reuse atom representations and rebuild affected derived outputs |
| [Incremental maintenance](start/incremental-maintenance.md) | Keep conversation topics and search current through edits and regrouping |

Each path includes an executable composition. The feature pages explain the
individual tools and the choices available when an application needs a
different implementation.

## Compose one knowledge library

Use [scoped references](start/architecture.md#shared-contracts) to carry identity
from ingestion through retrieval and evidence. Reuse
[semantic atoms](ingest/semantic-atoms.md) as source units, then declare the
inputs consumed by each derived output in the
[dependency planner](start/dependency-updates.md). Record completed outputs
before releasing downstream work.

Start with [installation](start/install.md), run an outcome example, then
replace its model and storage callbacks at the application boundary.

Browse the [algorithm choices](start/algorithm-choices.md) for independently
selectable implementations with cited sources and workload tradeoffs.

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
