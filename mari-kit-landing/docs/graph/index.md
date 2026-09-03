# Graphs & projections

## Evaluation

| Feature | Cases | Result | Corpus result |
|---|---:|---:|---|
| [Entity resolution](entity-resolution.md#evaluation) | 1 | 1 / 1 pass | WDC Products not measured |
| [Graph recall and communities](graph-processing.md#evaluation) | 5 | 5 / 5 pass | QASC/KILT/DocRED not measured |
| [Projections](projections.md#evaluation) | 2 | 2 / 2 pass | Throughput not measured |
| [Bitemporal facts](graph.md#evaluation) | 2 | 2 / 2 pass | Temporal QA not measured |

| Operation | Structure |
|---|---|
| Resolve entities | Field contributions plus link/review thresholds |
| Query temporal facts | Valid-time and transaction-time intervals |
| Expand retrieval | Authorized Personalized PageRank and passage projection |
| Aggregate a corpus | Connected communities and bounded map/reduce reports |
| Rebuild derived views | Ordered event replay with stable build identity |

:::{collapse} Worked graph flow

| Starting object | Graph operation | Returned structure |
|---|---|---|
| Query-linked entity | Authorized PageRank | Ranked nodes with propagation scores |
| Ranked nodes | Passage projection | Evidence passages with source-node trace |
| Temporal assertion | Bitemporal query | Facts valid and known at requested times |
| Event log | Projection replay | Derived state and stable build identity |
:::


```{toctree}
:maxdepth: 1

entity-resolution
graph-processing
projections
graph
```
