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
| Proactive memory | `yifannnwu/proactive-memory-agent` | Apache-2.0; permissive lifecycle reference | `ContextProvider`, `ContextRequest`, `LifecycleEvent` |
| Structured documents | `docling-project/docling` | MIT; permissive document-model reference | `StructuredDocument`, `DocumentRegion`, `TableCell` |
| Semantic schemas | `linkml/linkml`, `RDFLib/pySHACL` | Apache-2.0; permissive schema and validation references | `KnowledgeSchema`, `validate_records` |
| Portable bundles | `MacPaw/portable-memory` | MIT; permissive bundle and tombstone reference | `KnowledgeBundle`, `export_bundle`, `verify_bundle` |
| Signed portable memory | `apertomemory/apertomemory` | MIT; permissive interoperability reference | Future signing/encryption adapter; no crypto in core |
| Trust and scope | `quantifylabs/aegis-memory` | Apache-2.0; permissive policy reference | `MemoryWrite`, `evaluate_write`, `ScopePolicy` |
| Memory poisoning | `Digital-Trust-Lab/mp-bench` | Apache-2.0; permissive evaluation corpus | Write/retrieval attack evaluation; no detector copied |
| Task-level memory evaluation | `microsoft/STATE-Bench` | MIT; permissive metrics reference | `TaskOutcome`, `compare_task_outcomes` |
| Memory capability evaluation | `mazaiying/AgentMemBench` | MIT code; MemDialogue data is ODC-By 1.0 | Future corpus adapter; code not vendored |
| Structured code knowledge | `DeusData/codebase-memory-mcp` | MIT; permissive graph and evaluation reference | `CodeSymbol`, `CodeEdge`, `impacted_symbols` |
| Lifecycle capture | `Barsoomx/engram` | Apache-2.0; permissive session-hook reference | `ContextProvider` lifecycle boundary |
| General graph algorithms | `networkx/networkx` | BSD-3-Clause; permissive differential oracle | Traversal, paths, components, centrality, link prediction, SimRank, interchange |
| Prize-collecting subgraphs | `fraenkel-lab/pcst_fast` | MIT; permissive algorithm and adapter reference | `prize_guided_subgraph` is a distinct dependency-free heuristic; exact adapter remains optional |
| Construction quality | `kracr/kg-quality-metric` | Apache-2.0; permissive evaluation reference | `inspect_graph_quality`, graph construction evaluation boundaries |
| RDF interchange | `RDFLib/rdflib` | BSD-3-Clause; permissive interoperability oracle | `to_rdflib` |
| Entity blocking | `dedupeio/dedupe` | MIT; permissive blocking reference | `candidate_pairs`, `cluster_matches` |
| BM25 scoring | `dorianbrown/rank_bm25` | Apache-2.0; permissive equation and fixture reference | `BM25Index`, analyzer injection, score explanations; Mari retains its positive Robertson--Walker IDF variant |
| Constrained/submodular selection | `decile-team/submodlib` | MIT; permissive greedy-marginal-gain reference | `select_context_diverse`; Mari adds caller groups, multiple budgets, and complete decision traces |
| Interval queries | `chaimleib/intervaltree` | Apache-2.0; permissive half-open-overlap reference | `grouped_interval_overlaps`; Mari uses a dependency-free grouped sweep over datetime intervals |
| Markdown blocks | `executablebooks/markdown-it-py` at `bff75ed` | MIT; permissive token/span oracle | `parse_markdown`; block kinds and four line spans differentially matched |
| HTML recovery | `html5lib/html5lib-python` at `fd4f032` | MIT; permissive HTML5 tree oracle | `parse_html`; heading and table-cell text differentially matched |
| Delimited data | `frictionlessdata/frictionless-py` at `5debad3` | MIT; permissive schema/dialect reference | `parse_delimited`, positioned record issues, caller identity fields |
| Incremental syntax trees | `tree-sitter/py-tree-sitter` at `2e556e5` and `tree-sitter/tree-sitter-python` at `26855ea` | MIT; permissive syntax/span oracle | `SourceCoordinateMap`, `parse_python`; three definitions and UTF-8 byte spans differentially matched |
| PDF extraction | `py-pdf/pypdf` at `a667e9d` | BSD-3-Clause; permissive page/text visitor reference | Neutral `StructuredDocument` adapter target; no PDF decoder is bundled |

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

The first-pass lifecycle additions are clean-room, standard-library implementations. No files from the checked-out repositories are copied into `mari_components`; the repositories supply observable behavior, data-model comparisons, benchmark adapters, and future conformance fixtures.

The callback-driven graph algorithms were differentially checked against the
shallow NetworkX checkout for weighted shortest paths, connected components,
degree, closeness, betweenness, Jaccard, Adamic--Adar, and SimRank. NetworkX and
RDFLib projection round trips were also executed locally. Mari keeps its own
smaller callback APIs and does not vendor either library.

The composition pass additionally checked Mari's multi-predecessor breadth-first
results against NetworkX predecessor and distance output. BM25 term-frequency
normalization and length normalization were checked against the Apache-2.0
`rank_bm25` implementation after substituting Mari's documented positive IDF;
per-term explanations sum exactly to returned search scores.

The second composition pass inspected Submodlib's cost-sensitive greedy and
marginal-gain interfaces and IntervalTree's half-open overlap behavior. Mari's
implementations remain smaller value/callback algorithms and do not vendor the
libraries or claim their optimized data structures.

The ingestion pass compared Markdown block kinds and line spans with
Markdown-It-Py, HTML heading/table text with html5lib, and Python definition
names plus UTF-8 byte spans with Tree-sitter. The fixtures matched `4/4`, `5/5`,
and `3/3`, respectively. Frictionless and pypdf inform adapter and diagnostic
boundaries; Mari does not claim their complete format coverage.
