# Graph tools

## Graph operations

Graph algorithms operate on caller-owned topology. Start with scoped IDs and
authorized adjacency, then select the smallest operation that answers the
question. Use traversal for reachability, ranking for relative importance, and
evidence projection to return source-backed context.

For change maintenance, share `DependencyKey` identities with
[dependency-aware updates](../start/dependency-updates.md). A graph walk finds
potentially affected outputs. The planner uses input fingerprints and completed
receipts to decide which outputs need work. Temporal filters and access checks
remain explicit inputs to each operation.

| Operation | Structure |
|---|---|
| Resolve entities | Field contributions plus link/review thresholds |
| Query temporal facts | Valid-time and transaction-time intervals |
| Expand retrieval | Authorized Personalized PageRank and passage projection |
| Aggregate a corpus | Connected communities and bounded map/reduce reports |
| Rebuild derived views | Dependency planning plus ordered event replay |
| Validate semantic records | Versioned concepts, properties, relations, and violations |
| Inspect arbitrary topology | Traversal, paths, reachability, components, and cycles |
| Select evidence | Bounded seed expansion and prize-guided connected subgraphs |
| Propose links | Common-neighbor, Jaccard, and Adamic--Adar scores |
| Rank structure | Degree, closeness, betweenness, HITS, and Personalized PageRank |
| Compare graphs | Explicit node/edge additions, removals, and structural drift |
| Diagnose quality | Orphans, dangling edges, duplicates, self-loops, and density |
| Construct candidates | Caller-defined blocking, pair scoring, and clustering |
| Move between libraries | Loss-visible NetworkX, GraphML, and JSON-LD projections |

:::{collapse} Example graph flow

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
traversal-paths
subgraph-selection
link-prediction
structural-ranking
graph-diff-quality
construction-tools
temporal-provenance
interoperability
graph-processing
projections
graph
```
