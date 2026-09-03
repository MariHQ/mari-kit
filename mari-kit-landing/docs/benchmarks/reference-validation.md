# Reference validation and licenses

Mari's implementations are independent, small Python boundaries. Upstream repositories are used to verify formulas, ordering, thresholds, and public fixtures. They are not runtime dependencies and their code is not vendored.

## Permissive validation references

These implementations declare MIT or Apache-2.0 terms and may be used for behavioral comparisons:

- Faiss (MIT): dense search and IVF-PQ.
- hnswlib (Apache-2.0): HNSW search.
- RAPTOR (MIT): recursive summary trees.
- Self-RAG (MIT): reflection-token scoring.
- HippoRAG (MIT): graph retrieval.
- Graphiti (Apache-2.0): temporal graph behavior.
- A-MEM (MIT): note evolution.
- Mem0 (Apache-2.0): memory mutation planning.
- LightMem (MIT): topic segmentation and consolidation.
- MemoryOS (Apache-2.0): tiered memory.
- Voyager (MIT): persistent procedures.
- DSPy (MIT): metric-driven compilation.
- Agentic Context Engine (Apache-2.0): procedural regression workflows.
- RRC-DSCD (MIT): document contradiction detection.
- ContraDoc (Apache-2.0): contradiction evaluation, subject to source-document terms.

## Inspect-only references

These repositories are non-permissive or do not declare a repository license. Mari uses only published papers, equations, and black-box observable behavior for conformance:

- SPLADE: CC BY-NC-SA 4.0.
- SparseCL: no declared repository license found.
- HyDE: no declared repository license found.
- CRAG: no declared repository license found.

```{admonition} Boundary
:class: warning
No inspect-only code, weights, or fixtures are shipped in Mari. `SparseVectorIndex` accepts weights produced by the caller and therefore does not contain a SPLADE model implementation.
```

## What conformance means

The unit suite checks deterministic ranking, tie handling, filtering before document scoring, interval boundaries, contiguous replay, revision conflicts, metric formulas, and regression-gate behavior. Corpus benchmarks then measure task quality, cost, latency, and safety. Agreement with a reference implementation is evidence about a boundary—not proof that a complete upstream system has been reproduced.
