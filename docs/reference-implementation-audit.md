# Reference implementation and license audit

Mari reimplements small, model-neutral algorithm boundaries. Reference repositories are used for equation, ordering, threshold, and fixture conformance; they are not runtime dependencies.

| Algorithm family | Reference | License decision | Mari boundary |
|---|---|---|---|
| Dense, IVF-PQ | `facebookresearch/faiss` | MIT; permissive validation reference | `DenseFlatIndex`, `IVFPQIndex` |
| HNSW | `nmslib/hnswlib` | Apache-2.0; permissive validation reference | `HNSWIndex` |
| SPLADE | `naver/splade` | CC BY-NC-SA 4.0; inspect only, no copied code or weights | `SparseVectorIndex` accepts caller-produced weights |
| RAPTOR | `parthsarthi03/raptor` | MIT; permissive validation reference | `build_summary_tree` |
| Self-RAG | `AkariAsai/self-rag` | MIT; permissive validation reference | `score_self_rag_candidate` |
| HippoRAG | `OSU-NLP-Group/HippoRAG` | MIT; permissive validation reference | `personalized_pagerank`, `project_graph_scores` |
| Graphiti/Zep | `getzep/graphiti` | Apache-2.0; permissive temporal-model reference | `TemporalFact`, `query_temporal_facts` |
| A-MEM | `agiresearch/A-mem` | MIT; permissive validation reference | `plan_note_evolution` |
| Mem0 | `mem0ai/mem0` | Apache-2.0; permissive validation reference | `plan_memory_mutations` |
| LightMem | `zjunlp/LightMem` | MIT; permissive validation reference | `hybrid_topic_segments` |
| MemoryOS | `BAI-LAB/MemoryOS` | Apache-2.0; permissive tiering reference | `plan_consolidation` |
| Voyager | `MineDojo/Voyager` | MIT; permissive skill-library reference | `learn_procedure` |
| DSPy | `stanfordnlp/dspy` | MIT; permissive optimizer/reference | `compile_configurations` |
| Agentic Context Engine | `kayba-ai/agentic-context-engine` | Apache-2.0; permissive patch/gate reference | `regression_gate` and procedure proposals |
| SparseCL | `chenhongji/SparseCL` | No declared license; equations and observable outputs only | `sparse_contradiction_score`, `rank_sparse_contradictions` |
| RRC-DSCD | `Richard-Zhang1127/RRC-DSCD` | MIT; permissive validation reference; paper/repo reward discrepancy documented separately | DSCD verification module |
| ContraDoc | `ddhruvkr/CONTRADOC` | Apache-2.0; permissive dataset and validation reference, subject to source-document terms | document contradiction evaluation |
| HyDE | `texttron/hyde` | No repository license detected; inspect only | `hypothetical_document_embedding` |
| CRAG | `HuskyInSalt/CRAG` | No repository license detected; inspect only | `plan_corrective_retrieval` |

## Connector references

| Reference | License decision | Mari contribution |
|---|---|---|
| `run-llama/llama_index` | MIT; permissive catalog/reference | Provider coverage audit for cloud stores, Microsoft drives, and RSS |
| `dlt-hub/dlt` | Apache-2.0; permissive reference | SDK-neutral object listing/reading boundary for S3, GCS, and Azure Blob |
| `meltano/sdk` | Apache-2.0; permissive reference | Singer RECORD/STATE interoperability boundary |
| `Unstructured-IO/unstructured` | Apache-2.0; permissive reference | Separation of source ingestion from downstream parsing |

Mari's connector implementations use provider HTTP contracts and independent
normalization code. No upstream connector code or optional SDK dependency is
vendored.

For entries marked inspect-only, Mari is based on the published mathematics and independently written conformance cases. For permissive references, compatible licensing permits comparison, but Mari still keeps independent APIs and tests rather than vendoring the systems.
