# Graphs & projections

## Choose a graph operation


| Operation | Structure |
|---|---|
| Resolve entities | Field contributions plus link/review thresholds |
| Query temporal facts | Valid-time and transaction-time intervals |
| Expand retrieval | Authorized Personalized PageRank and passage projection |
| Aggregate a corpus | Connected communities and bounded map/reduce reports |
| Rebuild derived views | Ordered event replay with stable build identity |
| Validate semantic records | Versioned concepts, properties, relations, and violations |

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
semantic-schemas
graph-processing
projections
graph
```
