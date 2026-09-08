# Algorithm choices

Mari Kit is a collection of independently selectable algorithms for knowledge
and memory workloads. This guide covers the whole package: retrieval, subset
selection, parsing, memory, graph analysis, agent experience, maintenance,
verification, and evaluation. Similar methods remain available because their
tradeoffs differ. Each workload table names the public implementation and links
to its detailed behavior and sources.

The [complete module and API index](https://kit.mari.guru/start/algorithm-inventory.html)
accounts for every public implementation module, including the contracts,
connectors, and adapters that support algorithms. Module paths in the tables are
relative to `mari_kit`. The index links definitions to inspected source
lines. A source citation identifies provenance or a related method. Individual
pages explain which computations Mari implements and which model calls the host
supplies.

## Find a choice by workload

| Workload | Compare |
|---|---|
| [Retrieve candidates](#retrieve-candidates) | Lexical, sparse, dense, approximate, multi-vector, and graph retrieval |
| [Select useful context](#select-useful-context) | Relevance, MMR, coverage, diversity, cost, and source structure |
| [Adapt a retrieval session](#adapt-a-retrieval-session) | HyDE, RAPTOR, MemWalker, CRAG, FLARE, Self-RAG, and DRIFT |
| [Parse and align knowledge](#parse-and-align-knowledge) | Structured parsers, semantic atoms, diff algorithms, and byte chunking |
| [Organize memory](#organize-memory) | Admission, mutation, salience, heat, LFU, consolidation, and evolution |
| [Analyze and construct graphs](#analyze-and-construct-graphs) | Paths, communities, entity resolution, linkage, time, and provenance |
| [Learn from agent activity](#learn-from-agent-activity) | Episodes, intents, process mining, comparisons, procedures, and feedback |
| [Maintain changing knowledge](#maintain-changing-knowledge) | Snapshot planning, indexed updates, lineage, reversible aggregates, and replay |
| [Assess evidence and decisions](#assess-evidence-and-decisions) | Grounding, contradiction, consensus, trust, and authority |
| [Evaluate a choice](#evaluate-a-choice) | Retrieval, graph, memory, statistical, and configuration comparisons |
| [Supply integration boundaries](#supply-integration-boundaries) | Source adapters, identity, stores, schemas, and portability |

## Retrieve candidates

| Choice and public implementation | Useful workload and tradeoff | Details and sources |
|---|---|---|
| `retrieval.indexes.BM25Index`, `ArtifactBM25Index`, `RevisionBM25Index` | Exact terms, identifiers, and symbols with positive-IDF scoring. Artifact/revision wrappers preserve their respective identities. | [Lexical indexing](https://kit.mari.guru/retrieve/retrieval.html), [BM25](https://doi.org/10.1561/1500000019) |
| `algorithms.lexical.BM25VariantIndex` | Compare rank_bm25 Okapi, L, and Plus formulas for length/repetition effects. L/Plus can score nonmatches above zero. | [A01](#a01-bm25-alternatives), [rank_bm25][bm25] |
| `retrieval.indexes.SparseVectorIndex` | Exact search over caller-supplied sparse weights. The host supplies lexical or learned sparse representations. | [Sparse indexing](https://kit.mari.guru/retrieve/retrieval.html), [SPLADE representation research](https://arxiv.org/abs/2107.05720) |
| `retrieval.indexes.DenseFlatIndex` | Exact vector-search baseline for bounded corpora. Search examines the candidate vectors. | [Dense indexing](https://kit.mari.guru/retrieve/retrieval.html), [DPR](https://arxiv.org/abs/2004.04906) |
| `retrieval.indexes.HNSWIndex`, `IVFPQIndex` | Approximate graph search or coarse partitioning with product quantization. Measure recall against the flat index. | [Index behavior](https://kit.mari.guru/retrieve/retrieval.html), [HNSW](https://doi.org/10.1109/TPAMI.2018.2889473), [PQ](https://doi.org/10.1109/TPAMI.2010.57) |
| `retrieval.muvera.encode_fde`, `retrieval.index.build_index` / `search_index`, `retrieval.maxsim.exact_maxsim` | Fixed-dimensional candidate generation for token-level multi-vector retrieval followed by exact late-interaction reranking. | [MUVERA composition](https://kit.mari.guru/retrieve/retrieval.html), [MUVERA](https://arxiv.org/abs/2405.19504), [ColBERT](https://arxiv.org/abs/2004.12832) |
| `retrieval.polarquant.train_polar` / `encode_polar` / `polar_scores` | Mari's specific packed block-2 Polar codec for MUVERA FDE candidate scoring. Quantization trades representation detail for compactness. | [Codec behavior](https://kit.mari.guru/retrieve/retrieval.html), [Mari implementation][mari-polar] |
| `retrieval.atoms.aggregate_atom_hits`, `maxsim_section_score` | Aggregate atom hits to parent sections or score section token vectors. Parent aggregation and true MaxSim answer different scoring questions. | [Atom and section retrieval](https://kit.mari.guru/ingest/semantic-atoms.html), [ColBERTv2](https://arxiv.org/abs/2112.01488) |
| `retrieval.contradiction.rank_sparse_contradictions`, `sparse_contrastive_losses` | Retrieve same-topic contradiction candidates using similarity and difference sparsity. The training-loss helper leaves model training external. | [SparseCL boundary](https://kit.mari.guru/retrieve/contradiction-retrieval.html), [SparseCL](https://arxiv.org/abs/2406.10746) |
| `retrieval.graph.personalized_pagerank`, `project_graph_scores` | Propagate caller seed weights through allowed topology and project node scores to passages. | [Graph recall](https://kit.mari.guru/graph/graph-processing.html), [HippoRAG](https://arxiv.org/abs/2405.14831) |
| `algorithms.graph_retrieval.hipporag_seed_weights`, `expand_typed_links` | Build fact/entity/dense seeds before propagation, or perform one entity/semantic/causal expansion step. | [A06](#a06-hipporag2-seed-construction), [A11](#a11-typed-link-expansion), [HippoRAG][hippo], [Hindsight][typed] |
| `retrieval.fusion.reciprocal_rank_fusion` | Combine ranked lists whose score scales differ. Rank fusion discards score magnitude. | [Fusion](https://kit.mari.guru/retrieve/retrieval.html), [RAG-Fusion](https://arxiv.org/abs/2402.03367) |
| `algorithms.graph_retrieval.rank_candidate_union` | Score a union using one embedding space or one shared reranker. Explicit source identity handles cross-collection results. | [A21](#a21-common-space-union-ranking), [haiku.rag][union] |
| `algorithms.graph_retrieval.rank_graph_distances`, `rank_episode_mentions` | Prefer supplied graph locality or episode frequency, with explicit handling of missing values. | [A12](#a12-graph-distance-and-episode-mention-ranking), [Graphiti][graphiti] |

## Select useful context

| Choice and public implementation | Useful workload and tradeoff | Details and sources |
|---|---|---|
| `retrieval.fusion.maximal_marginal_relevance` | Balance query relevance against similarity to selected items. A direct option for repetitive search results. | [MMR usage](https://kit.mari.guru/retrieve/retrieval.html), [Mari implementation][mari-fusion] |
| `retrieval.composition.select_context`, `select_context_diverse` | Select artifact-neutral items with budgets, constraints, and explicit decision traces. Diversity-aware selection exposes candidate gains per round. | [Context selection](https://kit.mari.guru/retrieve/context.html), [submodular maximization](https://doi.org/10.1007/BF01588971) |
| `algorithms.subsets.FacilityLocation` | Represent the candidate collection by maximizing best-covered similarity per represented row. Optional query caps focus coverage. | [A02](#a02-subset-objectives), [Submodlib][submodlib] |
| `algorithms.subsets.LogDeterminant` | Favor distinct vector directions when selecting memories or evidence. Relevance and mandatory retention constraints need explicit treatment. | [A02](#a02-subset-objectives), [DPPs](https://arxiv.org/abs/1207.6083) |
| `algorithms.subsets.SetCover`, `ProbabilisticSetCover` | Cover caller-defined concepts with binary or probabilistic incidence and optional concept weights. | [A02](#a02-subset-objectives), [Submodlib][submodlib] |
| `algorithms.subsets.maximize_subset` | Select naive, lazy, stochastic, or lazier greedy independently of the objective. Lazy modes require submodularity. | [A03](#a03-greedy-optimizer-choices), [Submodlib optimizers][greedy] |
| `retrieval.context.assemble_context`, `retrieval.composition.hydrate_hits` | Resolve IDs and assemble bounded source content with exclusions and missing-hit traces. | [Context envelopes](https://kit.mari.guru/retrieve/context.html), [Mari context implementation][mari-context] |
| `retrieval.atoms.assemble_atom_context`, `retrieval.structure.expand_structured_context` | Expand retrieved atoms into neighboring context or preserve section structure, exact spans, and original hits. | [Atom context](https://kit.mari.guru/ingest/semantic-atoms.html), [evidence context](https://kit.mari.guru/retrieve/evidence-context.html), [haiku.rag][union] |
| `algorithms.graph_retrieval.weighted_chunk_polling` | Allocate descending per-parent chunk quotas and redistribute unused quota. Maximum denotes a parent quota. | [A08](#a08-weighted-chunk-polling), [LightRAG][polling] |
| `retrieval.research.selective_compression`, `algorithms.compression.select_surprising_words` | Compare caller-scored sentence selection with token-surprisal word selection. Both produce extractive content. | [RECOMP-style boundary](https://kit.mari.guru/retrieve/adaptive-retrieval.html), [RECOMP](https://arxiv.org/abs/2310.04408), [A13](#a13-source-preserving-surprisal-selection), [LightMem][lightmem] |
| `knowledge.compaction.plan_evidence_compaction`, `knowledge.multimodal.select_evidence_assets` | Preserve evidence groups through compaction and bind image/page/media assets to retained evidence. | [Evidence context](https://kit.mari.guru/retrieve/evidence-context.html), [haiku.rag][union] |

Log-determinant and facility location answer different questions. Log-determinant
rewards distinct contributions in the selected feature space. Facility location
rewards representation of the broader supplied collection. Explicit set cover
is useful when the host can name the requirements it needs covered. MMR combines
relevance and redundancy directly. None of these choices establishes factual
correctness or independent corroboration from embeddings alone.

## Adapt a retrieval session

| Choice and public implementation | Useful workload and tradeoff | Details and sources |
|---|---|---|
| `retrieval.research.hypothetical_document_embedding` | Embed a generated hypothetical answer/document to change the query representation. Generation and embedding callbacks belong to the host. | [Construction](https://kit.mari.guru/retrieve/retrieval-construction.html), [HyDE](https://arxiv.org/abs/2212.10496) |
| `retrieval.research.build_summary_tree`, `walk_summary_tree` | Build a recursive summary hierarchy and navigate it with bounded caller decisions. | [Tree construction and navigation](https://kit.mari.guru/retrieve/retrieval-construction.html), [RAPTOR](https://arxiv.org/abs/2401.18059), [MemWalker](https://arxiv.org/abs/2310.05029) |
| `retrieval.research.plan_corrective_retrieval`, `plan_active_retrieval` | Select corrective retrieval actions from relevance signals or additional queries from uncertain generated content. | [Adaptive policies](https://kit.mari.guru/retrieve/adaptive-retrieval.html), [CRAG](https://arxiv.org/abs/2401.15884), [FLARE](https://arxiv.org/abs/2305.06983) |
| `verification.research.score_self_rag_candidate` | Combine caller-supplied reflection signals to rank a candidate. Reflection generation and the complete Self-RAG model remain external. | [Self-RAG boundary](https://kit.mari.guru/retrieve/adaptive-retrieval.html), [Self-RAG](https://arxiv.org/abs/2310.11511) |
| `algorithms.search.drift_search` | Prime questions, expand ranked follow-ups within budgets, and reduce completed answers. | [A07](#a07-drift-action-search), [GraphRAG DRIFT][drift] |
| `retrieval.sufficiency.assess_context_sufficiency`, `parse_retrieval_gap_queries`, `evaluate_context_contribution` | Check explicit requirements, propose gap queries, and measure utility relative to consumed context. | [Sufficiency and contribution](https://kit.mari.guru/retrieve/context-lifecycle.html), [PlugMem](https://arxiv.org/abs/2603.03296) |
| `retrieval.disclosure.evaluate_disclosure`, `expand_disclosure`, `lifecycle.select_intervention` | Apply conditional disclosure, progressively expand source detail, or select a lifecycle intervention. Authorization remains a separate host input. | [Lifecycle and disclosure](https://kit.mari.guru/retrieve/context-lifecycle.html), [Nocturne](https://github.com/Dataojitori/nocturne_memory) |
| `retrieval.contextual.contextual_representation`, `pool_token_spans` | Attach validated context to chunks or pool supplied token vectors across source spans. | [Contextual representations](https://kit.mari.guru/retrieve/context-lifecycle.html), [Late Chunking](https://arxiv.org/abs/2409.04701) |

## Parse and align knowledge

| Choice and public implementation | Useful workload and tradeoff | Details and sources |
|---|---|---|
| `documents.markdown.parse_markdown`, `documents.html.parse_html`, `documents.records.parse_delimited` / `parse_json_lines` / `parse_json_array` | Parse text structure and records into source-addressable values. Format-specific fidelity is described in the parser guides. | [Source parsers](https://kit.mari.guru/ingest/parsers.html), [Mari parser implementation][mari-markdown] |
| `documents.code.parse_python`, `documents.impacted_symbols` | Extract Python symbols/references and find symbols affected by source changes. | [Code knowledge](https://kit.mari.guru/ingest/code-knowledge.html), [Codebase-Memory](https://github.com/DeusData/codebase-memory-mcp) |
| `documents.tables.normalize_table`, `documents.docling.adapt_docling_json` | Normalize table structure or adapt supplied Docling JSON with text, cells, page regions, and references. | [Structured documents](https://kit.mari.guru/ingest/structured-documents.html), [evidence context](https://kit.mari.guru/retrieve/evidence-context.html), [Docling](https://github.com/docling-project/docling) |
| `documents.atoms.semantic_atoms`, `content_defined_spans`, `active_atoms` | Use stable structural units, text-oriented content-defined fallback spans, and temporal versions. Text span boundaries differ from byte FastCDC. | [Semantic atoms](https://kit.mari.guru/ingest/semantic-atoms.html), [Mari atom implementation][mari-atoms] |
| `documents.sequence_diff.myers_diff`, `patience_diff`, `documents.atoms.align_atoms` | Compare minimum-edit alignment with unique-anchor alignment for changed sources. | [Revision alignment](https://kit.mari.guru/ingest/semantic-atoms.html), [Myers](https://doi.org/10.1007/BF01840446) |
| `algorithms.compression.fastcdc_chunks` | Deduplicate byte streams with read-pattern-independent content-defined boundaries and owned chunks. | [A14](#a14-byte-stream-fastcdc), [FastCDC][fastcdc] |
| `knowledge.facts.parse_facts`, `parse_claim_assessments`, `deduplicate_fact_candidates`, plus decisions/glossary/answers/summaries/refinement parsers | Validate caller-generated structured knowledge. Parsing a proposed claim provides a different guarantee from proving it. | [Task-specific parsers](https://kit.mari.guru/ingest/parsers.html), [FActScore](https://arxiv.org/abs/2305.14251), [QASPER](https://arxiv.org/abs/2105.03011) |
| `algorithms.search.refine_extraction` | Run bounded glean passes with explicit identity and merge policies. | [A09](#a09-extraction-gleaning), [LightRAG][glean] |
| `knowledge.sections.document_sections`, `knowledge.excerpt.excerpt`, `knowledge.tags.assign_tags`, `knowledge.links.extract_explicit_links` / `derive_links` | Select source sections/excerpts, assign normalized tags, and derive explicit links. | [Sections](https://kit.mari.guru/ingest/sections.html), [Tags](https://kit.mari.guru/ingest/tags.html), [Mari link implementation][mari-links] |

## Organize memory

| Choice and public implementation | Useful workload and tradeoff | Details and sources |
|---|---|---|
| `knowledge.admission.admit_candidate` | Accept, defer, reject, or quarantine from explicit admission signals and thresholds. | [Admission](https://kit.mari.guru/memory/admission.html), [Mari admission policy][mari-admission] |
| `knowledge.mutations.plan_memory_mutations`, `apply_memory_mutations` | Validate add/update/delete/no-op decisions against existing memories. The host supplies decisions and durable transactions. | [Memory mutations](https://kit.mari.guru/memory/memory-algorithms.html), [Mem0](https://arxiv.org/abs/2504.19413) |
| `knowledge.segmentation.hybrid_topic_segments`, `knowledge.consolidation.plan_consolidation` | Segment topic changes and choose bounded offline work from utility/cost signals. | [Consolidation](https://kit.mari.guru/memory/consolidation.html), [LightMem](https://arxiv.org/abs/2510.18866), [MemoryOS](https://arxiv.org/abs/2506.06326) |
| `knowledge.research.rank_salient_memories` | Combine recency, importance, and relevance using the existing salience policy. | [Memory organization](https://kit.mari.guru/memory/memory-organization.html), [Generative Agents](https://arxiv.org/abs/2304.03442) |
| `algorithms.temporal.recency_decay`, `dated_recency`, `temporal_proof_score` | Compare linear/exponential/neutral freshness and proportional temporal/proof boosts to relevance. | [A10](#a10-temporal-and-proof-ranking), [Hindsight][temporal] |
| `algorithms.memory.memory_heat`, `lfu_evictions`, `heat_promotions` | Raw visit/interaction/recency heat, least-frequency eviction, and above-threshold promotion are independent policies. | [A15](#a15-raw-heat-lfu-and-promotion), [MemoryOS][heat] |
| `knowledge.research.plan_note_evolution`, `algorithms.memory.evolve_neighborhood` | Compare the existing note-link plan with callback-proposed context/tag/link updates guarded by expected revisions. | [Note organization](https://kit.mari.guru/memory/memory-organization.html), [A18](#a18-neighborhood-memory-evolution), [A-MEM][amem] |
| `verification.research.decide_from_evidence_notes` | Decide an answer source from sequential evidence-note judgments supplied by the host. | [Evidence-note decisions](https://kit.mari.guru/memory/memory-organization.html), [Chain-of-Note](https://arxiv.org/abs/2311.09210) |
| `algorithms.memory.reduce_skill_feedback` | Reduce helpful/harmful/neutral feedback and explicit keep/update/delete/merge decisions with provenance. | [A19](#a19-feedback-and-skill-deduplication), [ACE][ace] |
| `governance.propose_promotion`, `plan_retention`, `evaluate_purpose` | Propose scope changes and retention actions under caller policies. These are planning decisions with host-owned persistence. | [Scopes](https://kit.mari.guru/memory/scopes.html), [Retention](https://kit.mari.guru/govern/retention.html), [Mari governance implementation][mari-governance] |

## Analyze and construct graphs

| Choice and public implementation | Useful workload and tradeoff | Details and sources |
|---|---|---|
| `graph.traversal.breadth_first`, `k_hop_nodes`, `shortest_path`, `traverse_edges`, `predecessor_dag` | Reachability, paths, edge-aware traversal, and alternate predecessor explanations. | [Traversal and paths](https://kit.mari.guru/graph/traversal-paths.html), [Dijkstra](https://doi.org/10.1007/BF01386390) |
| `graph.traversal.connected_components`, `directed_cycles`, `algorithms.graphs.condense_graph` | Identify connectivity, cycles, or strongly connected components and their condensation DAG. | [Traversal](https://kit.mari.guru/graph/traversal-paths.html), [A20](#a20-graph-structural-alternatives), [NetworkX][structure] |
| `algorithms.graphs.transitive_reduction_edges`, `cohesive_subgraph` | Reduce redundant DAG edges or select topological k-core/k-truss membership. | [A20](#a20-graph-structural-alternatives), [NetworkX][structure] |
| `graph.subgraphs.bounded_seed_expansion`, `prize_guided_subgraph`, `algorithms.graphs.prize_collecting_forest` | Compare bounded expansion, the local greedy prize heuristic, and the native PCST approximation for connecting useful evidence. | [Subgraph selection](https://kit.mari.guru/graph/subgraph-selection.html), [A04](#a04-prize-collecting-forest-solver), [G-Retriever](https://arxiv.org/abs/2402.07630), [pcst_fast][pcst] |
| `graph.centrality.degree_centrality`, `closeness_centrality`, `betweenness_centrality`, `hits` | Rank local connectivity, distance, bridge position, or hub/authority structure. Different centralities encode different notions of importance. | [Structural ranking](https://kit.mari.guru/graph/structural-ranking.html), [Brandes](https://doi.org/10.1080/0022250X.2001.9990249) |
| `graph.similarity.score_link_candidates`, `simrank_scores` | Score common-neighbor/Jaccard/Adamic–Adar links or recursive structural similarity. | [Link prediction](https://kit.mari.guru/graph/link-prediction.html), [SimRank](https://doi.org/10.1145/775047.775126) |
| `graph.communities.leiden_communities`, `algorithms.graphs.louvain_partition`, `hierarchical_leiden_partition` | Compare the historical local-modularity heuristic, NetworkX Louvain, and native hierarchical Leiden. Only the native adapter provides full hierarchical Leiden. | [Community behavior](https://kit.mari.guru/graph/graph-processing.html), [A05](#a05-louvain-and-hierarchical-leiden), [Louvain][louvain], [Leiden](https://doi.org/10.1038/s41598-019-41695-z) |
| `graph.communities.build_community_reports`, `map_reduce_reports` | Generate community reports and reduce report-level query results through bounded callbacks. | [Corpus aggregation](https://kit.mari.guru/graph/graph-processing.html), [GraphRAG](https://arxiv.org/abs/2404.16130) |
| `graph.resolution.fellegi_sunter_score`, `resolve_entity` | Combine field-level agreement evidence into match/review/nonmatch decisions. | [Entity resolution](https://kit.mari.guru/graph/entity-resolution.html), [Fellegi–Sunter](https://doi.org/10.1080/01621459.1969.10501049) |
| `graph.construction.candidate_pairs`, `explain_candidate_pairs`, `cluster_matches`, `inspect_clusters` | Build blocked pairs, inspect pair provenance, and cluster supplied match links with diagnostics. | [Construction tools](https://kit.mari.guru/graph/construction-tools.html), [Dedupe](https://github.com/dedupeio/dedupe) |
| `algorithms.linkage.learn_blocking`, `acquire_disagreement` | Learn a predicate disjunction under coverage/cost constraints and acquire informative matcher/blocker disagreements. | [A16](#a16-learned-blocking-and-active-pair-acquisition), [Dedupe][blocking] |
| `algorithms.linkage.centroid_clusters`, `greedy_matching`, `gazette_matching` | Compare same-entity clustering, one-to-one greedy assignment, and reusable-right-record lookup. | [A17](#a17-entity-clustering-and-matching-choices), [Dedupe][linkage] |
| `graph.temporal.query_temporal_facts`, `close_transaction`, `graph.temporal_tools.temporal_join`, `grouped_interval_overlaps` | Query valid/transaction time and join interval-bearing records. Interval semantics are explicit. | [Temporal graphs](https://kit.mari.guru/graph/graph.html), [Temporal operations](https://kit.mari.guru/graph/temporal-provenance.html), [Graphiti](https://github.com/getzep/graphiti) |
| `graph.provenance.trace_lineage`, `trace_lineage_edges`, `propagated_taints`, `graph.evidence_projection.project_graph_evidence` | Explain derivation paths, propagate taints, and project graph selections to bound evidence. | [Provenance](https://kit.mari.guru/graph/temporal-provenance.html), [Evidence projection](https://kit.mari.guru/graph/construction-tools.html), [Mari provenance][mari-provenance] |
| `graph.diagnostics.graph_diff`, `diff_records`, `diff_record_fields`, `inspect_graph_quality`, `knowledge.versions.resolve_version_families` | Inspect structural/field drift, graph quality, and revision families. Diagnostics describe supplied data. | [Graph differences](https://kit.mari.guru/graph/graph-diff-quality.html), [Version families](https://kit.mari.guru/graph/construction-tools.html), [Mari diagnostics][mari-diagnostics] |

## Learn from agent activity

| Choice and public implementation | Useful workload and tradeoff | Details and sources |
|---|---|---|
| `conversation_knowledge.segment_conversations`, `compile_episodes`, `conversation_topics.semantic_conversation_episodes`, `semantic_topic_groups`, `compile_topic_briefs` | Compare thread/time segmentation with embedding-based complete-link episode/topic grouping. Compilation uses supplied extraction/consolidation callbacks and revision-bound evidence. | [Conversation knowledge](https://kit.mari.guru/agents/conversation-knowledge.html), [LightMem](https://arxiv.org/abs/2510.18866), [Mari topic grouping][mari-topics] |
| `trajectories.normalize.normalize_steps`, `trajectories.adapters.normalize_openai_trajectory` / `normalize_anthropic_trajectory` / `normalize_otel_trajectory`, `trajectories.traces.normalize_genai_trace` | Normalize observed activity and preserve trace integrity before comparing behavior. These are format adapters and validators. | [Trajectory normalization](https://kit.mari.guru/agents/trajectory-mining.html), [Hodoscope](https://github.com/AR-FORUM/hodoscope), [OpenTelemetry GenAI](https://github.com/open-telemetry/semantic-conventions-genai) |
| `trajectories.episodes.segment_episodes`, `parse_turn_assessments`, `parse_episode_reflection` | Segment bounded activity and validate caller assessments/reflections. | [Trajectories](https://kit.mari.guru/agents/trajectories.html), [Reflexion](https://arxiv.org/abs/2303.11366) |
| `trajectories.process.mine_trajectory_process`, `trajectories.matching.trajectory_edit_distance`, `compare_trajectories` | Mine activity/transition frequencies and compare ordered execution paths. | [Process and path mining](https://kit.mari.guru/agents/trajectory-mining.html), [TraceRoutine](https://github.com/gurov/traceroutine), [AgentEvals](https://github.com/langchain-ai/agentevals) |
| `trajectories.invariants.mine_trajectory_invariants`, `check_trajectory_invariant`, `trajectories.sampling.select_diverse_trajectories` | Find observed invariants and choose varied traces for inspection. Observed invariants need held-out validation. | [Invariant mining and sampling](https://kit.mari.guru/agents/trajectory-mining.html), [Trace-to-Evals](https://github.com/a-bhimava/agent-trace-to-evals) |
| `trajectories.intents.aggregate_intents`, `summarize_intent_reviews`, `trajectories.intent_analysis.cluster_intents`, `detect_novel_intents`, `compare_intent_windows` | Aggregate inferred intents, cluster examples, detect novelty, and compare changing distributions. | [Intent analysis](https://kit.mari.guru/agents/intent-mining.html), [intent decomposition](https://aclanthology.org/2025.emnlp-main.949/), [Jensen–Shannon divergence](https://doi.org/10.1109/18.61115) |
| `trajectories.rubrics.score_trajectory_rubric`, `trajectories.experience.mine_outcome_associations`, `compare_reasoning_memories` | Apply explicit rubrics and compare outcome-associated reasoning memories with uncertainty estimates. | [Intent/rubric analysis](https://kit.mari.guru/agents/intent-mining.html), [Experience knowledge](https://kit.mari.guru/memory/experience-knowledge.html), [AdaRubric](https://arxiv.org/abs/2603.21362) |
| `trajectories.procedures.learn_procedure`, `trajectories.mine.parse_trajectory_analysis` | Turn supplied activity analysis into a procedure candidate. The callback/evaluation boundary determines quality. | [Procedures](https://kit.mari.guru/agents/procedures.html), [Procedural learning](https://kit.mari.guru/agents/procedural-learning.html), [Voyager](https://arxiv.org/abs/2305.16291) |
| `trajectories.workflows.match_reviewed_workflow`, `match_cached_response`, `decide_reviewed_workflow`, `start_speculative_retrieval` | Match reviewed workflows or cached answers and choose policy actions with explicit freshness checks. | [Workflow decisions](https://kit.mari.guru/govern/workflows.html), [GPTCache](https://aclanthology.org/2023.nlposs-1.24/) |
| `knowledge.experience.build_knowledge_use_manifest`, `parse_feedback_diagnoses`, `parse_experience_knowledge`, `parse_knowledge_change`, `knowledge.observations.inspect_knowledge_observations` | Record what knowledge an agent saw/used, diagnose feedback, and propose bounded edits. | [Experience knowledge](https://kit.mari.guru/memory/experience-knowledge.html), [PlugMem](https://arxiv.org/abs/2603.03296), [ReasoningBank](https://arxiv.org/abs/2509.25140) |

## Maintain changing knowledge

| Choice and public implementation | Useful workload and tradeoff | Details and sources |
|---|---|---|
| `dependencies.plan_dependency_updates`, `incremental.DependencyIndex` | Compare complete snapshot planning with an indexed affected frontier. Inputs, derivations, and completed receipts drive reuse/rebuild decisions. | [Dependency updates](https://kit.mari.guru/start/dependency-updates.html), [Incremental maintenance](https://kit.mari.guru/start/incremental-maintenance.html), [Mari planner][mari-dependencies] |
| `selections.plan_selection`, `complete_selection`, `grouping.reconcile_groups` | Track changes to selection membership and preserve group identity through split/merge/regrouping using member overlap. | [Incremental maintenance](https://kit.mari.guru/start/incremental-maintenance.html), [Mari grouping][mari-grouping] |
| `aggregates.DeltaAggregate`, `CountReducer`, `WeightedVectorReducer`, `LexicalStatisticsReducer`, `MembershipReducer` | Apply reversible keyed updates to counts, vectors, lexical statistics, or membership. Single-writer reference aggregates expose host persistence boundaries. | [Delta aggregates](https://kit.mari.guru/start/incremental-maintenance.html), [Mari reducers][mari-aggregates] |
| `documents.atoms.plan_atom_refresh`, `documents.dependencies.atom_dependencies`, `knowledge.freshness.assess_freshness`, `impacted_artifacts` | Relate source changes to atom work and evidence freshness. Structural refresh and artifact validity are separate decisions. | [Atom maintenance](https://kit.mari.guru/ingest/semantic-atoms.html), [Freshness](https://kit.mari.guru/govern/freshness.html), [Mari freshness][mari-freshness] |
| `platform.views.plan_view_refresh`, `platform.projections.replay_projection` | Plan derived-view refresh or rebuild projections from ordered events. | [Living views](https://kit.mari.guru/platform/living-views.html), [Projection replay](https://kit.mari.guru/graph/projections.html), [DBSP research context](https://arxiv.org/abs/2203.16684) |
| `sync.planning.plan_sync`, `stream_sync`, `sync.application.apply_sync_plan`, `connectors.events.coalesce_hints_ordered` | Reconcile complete/incremental source observations and coalesce ordered hints before canonical refetch. | [Sync planning](https://kit.mari.guru/ingest/sync.html), [Connectors](https://kit.mari.guru/ingest/connectors.html), [Mari sync][mari-sync] |
| `knowledge.fact_scans.pending_fact_sections`, `knowledge.assertions.plan_assertion_update`, `valid_at` | Select stale fact-scan sections and plan assertion revision history. | [Freshness](https://kit.mari.guru/govern/freshness.html), [Mari assertions][mari-assertions] |

## Assess evidence and decisions

| Choice and public implementation | Useful workload and tradeoff | Details and sources |
|---|---|---|
| `verification.scoring.harmonic_score`, `idea_completeness`, `score_grounded`, `verification.selection.select_best`, `verification.portfolio.best_of_n`, `verification.consensus.verdict_consensus` | Score supplied evidence signals, select candidate attempts, and aggregate verdicts. Numerical scoring remains separate from claim-generation quality. | [Verification](https://kit.mari.guru/govern/verification.html), [Self-consistency](https://arxiv.org/abs/2203.11171), [ALCE](https://arxiv.org/abs/2305.14627) |
| `knowledge.aggregation.weighted_mean`, `wilson_proportion`, `knowledge.scoring.grounding_coverage` | Aggregate evidence with explicit weights/uncertainty and measure cited support coverage. | [Numerical verification](https://kit.mari.guru/govern/verification.html), [Wilson interval](https://doi.org/10.1080/01621459.1927.10502953) |
| `verification.contradiction.validate_document_contradiction`, `document_contradiction_rewards` | Validate within-document contradiction evidence and reference-coverage rewards. Cross-source SparseCL retrieval is a separate choice. | [Document contradiction](https://kit.mari.guru/govern/document-contradiction.html), [reference coverage](https://aclanthology.org/2025.emnlp-main.67/) |
| `knowledge.evidence.validate_artifact_evidence`, `validate_located_evidence`, `knowledge.citations.inspect_citation_declarations`, `documents.validation.validate_region_evidence` | Check evidence identity, location, regions, and declared citation lifecycles. These checks verify structure and binding. | [Evidence](https://kit.mari.guru/govern/evidence.html), [Evidence context](https://kit.mari.guru/retrieve/evidence-context.html), [haiku.rag][union] |
| `governance.evaluate_write`, `inherit_taints`, `resolve_assertions` | Evaluate supplied trust signals, inherited taints, and explicit authority policies for competing assertions. | [Trust decisions](https://kit.mari.guru/govern/trust-writes.html), [Authority conflicts](https://kit.mari.guru/govern/authority-conflicts.html), [Mari governance][mari-governance] |
| `knowledge.changesets.validate_knowledge_changeset`, `knowledge.derivations.inspect_knowledge_derivations`, `knowledge.experience.inspect_knowledge_structure` | Validate grouped edits, derivation dependencies/feedback loops, and caller-designed knowledge-file structures. | [Experience validation](https://kit.mari.guru/memory/experience-knowledge.html), [Nanopublications](https://arxiv.org/abs/1809.06532) |
| `retrieval.decisions.filter_with_reasons`, `diagnose_candidate_history` | Trace inclusion/exclusion and cross-stage candidate decisions. | [Context decision traces](https://kit.mari.guru/retrieve/context.html), [Mari decision diagnostics][mari-decisions] |

## Evaluate a choice

| Choice and public implementation | Useful workload and tradeoff | Details and sources |
|---|---|---|
| `evaluation.metrics.evaluate_retrieval`, `reciprocal_rank`, `ndcg_at_k`, `set_metrics`, `boundary_metrics`, `classification_metrics` | Measure ranking, set coverage, segmentation, and classification under supplied labels. | [Evaluation](https://kit.mari.guru/platform/memory-evaluation.html), [Mari metrics][mari-metrics] |
| `evaluation.graph.evaluate_path`, `evaluate_link_prediction`, `evaluate_subgraph`, `evaluate_clustering`, `evaluate_graph_context`, `evaluate_grouped_coverage` | Evaluate path/edge/node recovery, clusters, graph-grounded context, and grouped requirements. | [Graph diagnostics and measures](https://kit.mari.guru/graph/graph-diff-quality.html), [Mari graph evaluation][mari-graph-eval] |
| `evaluation.statistics.compare_paired_metrics`, `evaluate_slices`, `summarize_review_reliability`, `summarize_repeated_trials` | Compare paired outcomes, slices, reviewer agreement, and repeated attempts with uncertainty. | [Outcome comparison](https://kit.mari.guru/platform/memory-evaluation.html), [Mari statistical implementation][mari-statistics] |
| `evaluation.metrics.compare_task_outcomes`, `evaluation.gates.regression_gate`, `agents.evaluation.evaluate_tools` / `evaluate_outcome` | Check task-level improvements, regression thresholds, and observed tool/outcome behavior. | [Task outcomes](https://kit.mari.guru/platform/memory-evaluation.html), [Mari gates][mari-gates] |
| `platform.compiler.compile_configurations` | Compare caller-supplied configurations against explicit metric objectives. The host defines the candidate search space and evaluation. | [Configuration compiler](https://kit.mari.guru/platform/compiler.html), [DSPy research context](https://arxiv.org/abs/2310.03714) |
| `evaluation.cases.load_beir_cases`, `load_fever_cases`, `load_longmemeval_cases`, `evaluation.catalog`, `evaluation.suites` | Load benchmark cases/catalogs for a consistent comparison. Dataset adapters supply cases rather than algorithm-quality claims. | [Memory evaluation](https://kit.mari.guru/platform/memory-evaluation.html), [LongMemEval](https://arxiv.org/abs/2410.10813) |

## Supply integration boundaries

These modules are part of the project and appear in the complete index. They
supply values, validation, I/O adapters, and execution boundaries rather than
alternative ranking objectives.

| Area | Public surfaces and purpose | Details and project sources |
|---|---|---|
| Identity and structure | `references`, `types`, `documents`, `schema`, `knowledge.artifacts`: IDs, revisions, source coordinates, document/region values, semantic records, and schema validation. | [Documents](https://kit.mari.guru/ingest/documents.html), [Schemas](https://kit.mari.guru/graph/semantic-schemas.html), [Artifacts](https://kit.mari.guru/platform/artifacts.html), [Mari package][mari-package] |
| Source adapters | `connectors`: Airtable, Asana, Box, Confluence, Dropbox, filesystem, GitHub, GitLab, Google Drive, Jira, JSON API, Linear, Microsoft Drive, Notion, object storage, RSS, Singer, Slack, Trello, Zendesk, and shared event/stream protocols. | [Connector capabilities](https://kit.mari.guru/ingest/connectors.html), [CloudEvents](https://github.com/cloudevents/spec), [Mari connectors][mari-connectors] |
| Graph and index interchange | `graph.interop`, `retrieval.serialization`: NetworkX/GraphML/JSON-LD/RDFLib/PyG projections and supported index serialization with explicit loss/compatibility checks. | [Graph interoperability](https://kit.mari.guru/graph/interoperability.html), [Index interfaces](https://kit.mari.guru/retrieve/retrieval.html), [NetworkX](https://github.com/networkx/networkx) |
| Contracts and storage | `contracts`, `http`, `errors`, `json`, `platform.stores`, `platform.pipeline`, `testing`: injected interfaces, immutable JSON, canonical serialization, reference stores, stage execution, and conformance checks. | [Contracts](https://kit.mari.guru/platform/contracts.html), [Stores](https://kit.mari.guru/platform/stores.html), [Pipelines](https://kit.mari.guru/platform/pipelines.html), [Mari package][mari-package] |
| Portable bundles | `portability.export_bundle`, `verify_bundle`, `plan_bundle_import`: integrity verification and import planning for knowledge artifacts and evidence. | [Portability](https://kit.mari.guru/platform/portability.html), [Portable Memory](https://github.com/MacPaw/portable-memory) |

## Run and inspect the implementations

```python
from mari_kit.algorithms.subsets import LogDeterminant, maximize_subset
from mari_kit.retrieval.indexes import BM25Index, DenseFlatIndex
from mari_kit.retrieval.fusion import maximal_marginal_relevance
from mari_kit.dependencies import plan_dependency_updates
```

Imports illustrate independent choices. The [feature guides](https://kit.mari.guru/)
show function signatures and runnable compositions. Use the
[complete module/API index](https://kit.mari.guru/start/algorithm-inventory.html)
to locate additional helpers, records, methods, and exact source definitions.
Base numerical implementations depend on NumPy. Native graph and centroid
operations are loaded lazily through `mari-kit[algorithm-solvers]`.

Some research-inspired boundaries consume model outputs or callbacks. The
library supplies the documented computation, validation, or plan. The host
supplies models, data, storage, authorization, and execution policy. Exact local
fixtures and published paper results answer different evaluation questions.

## Detailed source notes

The A01–A21 notes below retain the original stable sections for the September
algorithm additions. The workload tables above place those additions alongside
the pre-existing choices. Existing families have their detailed source and
implementation notes in the linked feature guides.

(a01-bm25-alternatives)=
## A01 — BM25 alternatives

`lexical.BM25VariantIndex` requires explicit `BM25Variant.OKAPI`, `.L`, or `.PLUS`
and caller-tokenized documents/query. It returns scores, matched flags, and
per-term explanations. It follows [rank_bm25's formulas][bm25], including Okapi's
negative-IDF epsilon floor and L/Plus nonmatching baselines. The existing
positive-IDF `BM25Index` remains a separate option.

Choose among them by retrieval evaluation, especially when document lengths or
term repetition vary. Scores are not interchangeable across variants/corpora.
`matching_only=True` removes baseline-only hits; `allowed_ids` restricts outputs,
while corpus statistics remain those of the index. Build separate indexes when
statistics themselves must be isolated. Empty corpora return no hits; all-empty
corpora and zero-length normalization yield finite zero/baseline scores instead
of upstream division errors. Query work is proportional to documents × terms.

(a02-subset-objectives)=
## A02 — Subset objectives

`subsets.FacilityLocation`, `SetCover`, `ProbabilisticSetCover`, and
`LogDeterminant` implement [Submodlib objective equations][submodlib]. Each offers
`evaluate(subset)` and `marginal_gain(subset, item)` over integer candidate indices.
Facility location uses represented-row × candidate similarities and sums each
row's best selected similarity. `query_similarities` adds FL1MI's cap
`eta * max(query similarity)` per represented row, allowing query-focused coverage.

Set cover uses binary item × concept incidence; probabilistic cover computes
`sum(weight * (1 - product(1-p)))`. Log determinant computes
`log det(K_A + regularization I)` for a symmetric PSD kernel and is zero for an
empty selection. Choose representation coverage, explicit concept coverage, or
kernel diversity according to the workload. Nonnegative kernels/weights and
valid probabilities are checked. These dense reference objectives recompute
values: logdet evaluation is cubic in selected size, and initial PSD validation
is cubic in ground-set size. Arbitrary logdet scaling is not necessarily monotone.
See also the project's [Submodlib paper](https://arxiv.org/abs/2202.10680).

(a03-greedy-optimizer-choices)=
## A03 — Greedy optimizer choices

`subsets.maximize_subset` accepts any deterministic objective callback, positive
costs, total budget, optional item limit, and `GreedyMethod.NAIVE`, `.LAZY`,
`.STOCHASTIC`, or `.LAZIER`. These adapt the [Submodlib optimizer family][greedy].
Results expose selected indices, marginal gains, costs, objective evaluation
counts, and remaining candidates.

Naive recomputes every feasible gain; lazy caches upper bounds; stochastic
samples candidates; lazier combines sampling and bounds. Lazy modes require
`assume_submodular=True`. Seeded sampling and index tie breaks are reproducible.
The sample size is `ceil(n/k * log(1/epsilon))`. Sampling guarantees require a
monotone submodular cardinality problem, not arbitrary costs. Gain/cost ranking
is a heuristic for budgets; no knapsack-optimality claim is made. A sampled
nonpositive best gain can stop with unsampled useful candidates remaining.

(a04-prize-collecting-forest-solver)=
## A04 — Prize-collecting forest solver

`graphs.prize_collecting_forest` adapts [pcst_fast][pcst] to caller node prizes
and edge **costs**. It returns original IDs/edges and prize/cost totals. A rooted
call fixes its required root; an unrooted call can request multiple clusters.
Choose it when valuable evidence requires intermediate connectors, including
zero-prize nodes. This is the native approximation, not an exact optimal solver.
The existing greedy selector remains useful as a different low-overhead choice.
Optional `allowed_nodes` induces the input graph before solving.

(a05-louvain-and-hierarchical-leiden)=
## A05 — Louvain and hierarchical Leiden

`graphs.louvain_partition` invokes [NetworkX Louvain][louvain];
`hierarchical_leiden_partition` invokes graspologic-native using the same engine
as [GraphRAG's hierarchical Leiden adapter][leiden]. Weighted edges, resolution,
seed, and optional allowed nodes are explicit. Leiden returns node/community,
level, parent, and final-membership records. Isolated nodes get singleton records;
`max_cluster_size` is a splitting target, not a strict guarantee.

Use Louvain for modularity partitions or hierarchical Leiden for multilevel
community workflows. Native library versions can change results despite a fixed
seed. The historical `graph.communities.leiden_communities` API is preserved and
now explicitly documented as local modularity improvement plus connected
splitting; it does not implement full Leiden aggregation.

(a06-hipporag2-seed-construction)=
## A06 — HippoRAG2 seed construction

`graph_retrieval.hipporag_seed_weights` implements the fact/entity/dense passage
seed calculation in [HippoRAG's graph search][hippo]. Fact scores are divided by
entity passage frequency, averaged over incident facts, and optionally limited
to the best linked entities. Passage scores are min-max normalized and scaled
by `passage_weight`. The result exposes each contribution separately.

Use this for graph recall combining extracted facts and dense passage evidence.
The caller provides embeddings, fact filtering, entity links, and graph edges.
Allowed IDs are required and filtered before passage normalization. Missing
entity frequencies use one; tied passage scores contribute zero. Feed positive
combined weights into `retrieval.personalized_pagerank`; choose a fallback when
all weights are zero. This ports seed construction, not HippoRAG2 end to end.

(a07-drift-action-search)=
## A07 — DRIFT action search

`search.drift_search` adapts [GraphRAG DRIFT][drift]: a primer supplies queries,
local search returns answers and follow-ups, incomplete actions are selected by
score or seeded randomness, and a reducer combines completed evidence. All model
and retrieval calls are supplied callbacks. The returned trace includes parent
indices, depth, completed/pending actions, and budget/exhaustion status.

Use this for exploratory graph search that can revise its questions. Exact query
strings are deduplicated to prevent cycles. `max_actions` limits local calls;
primer and reducer each run once outside that count. `max_depth` stops follow-up
expansion. Callbacks must bound their own result sizes and latency; callback
errors propagate. This is an explicit bounded adaptation, without GraphRAG's
provider prompts, database layer, or answer-quality claims.

(a08-weighted-chunk-polling)=
## A08 — Weighted chunk polling

`graph_retrieval.weighted_chunk_polling` follows [LightRAG's quota and polling
algorithm][polling]. Ordered parents receive descending linear chunk quotas;
unused allocation is redistributed by scanning highest-ranked parents first.
`maximum` is the highest-ranked parent quota, not a global cap: total allocation
is bounded by the sum of interpolated parent quotas.
It returns chunks, per-parent counts, and initial quotas. Use it when graph
hits have uneven numbers of attached chunks. Parent order and chunk order are
caller policy. Duplicates are retained by default; optional deduplication happens
after allocation and does not backfill, so output may be below budget.

(a09-extraction-gleaning)=
## A09 — Extraction gleaning

`search.refine_extraction` adapts [LightRAG's extraction and glean merge][glean]
to explicit initial/refinement callbacks, record identity, and merge policy.
It accumulates additions and revisions until the round budget, a continuation
callback, or unchanged merged records stops refinement. Use a longer-description
merge to resemble LightRAG's merge preference, or supply another policy.

The upstream path performs an extra extraction pass when enabled; Mari
explicitly generalizes this to a configurable bounded number of rounds. Records
must have stable equality and immutable values; merges must preserve identity.
There is no hidden model call, storage mutation, or assumption that an additional
pass improves extraction accuracy.

(a10-temporal-and-proof-ranking)=
## A10 — Temporal and proof ranking

`temporal.recency_decay`, `dated_recency`, and `temporal_proof_score` implement
[Hindsight's recency and multiplicative scoring][temporal]. Select linear decay
with a 0.1 floor, exponential half-life, or neutral 0.5. Date handling uses the
source's month/year span-length heuristic: age from period end, cap at neutral;
otherwise prefer occurrence start, mention, then end. Naive datetimes mean UTC.

Normalized relevance is multiplied by neutral-centered recency, proximity,
and log proof-count factors. Use this to make recency a proportional preference
without replacing relevance ranking. Dates/proximity/proof counts come from the
host. Invalid windows and reversed intervals raise instead of silently using
upstream fallbacks. Span length is a heuristic for coarse dates, not inferred
certainty about date granularity. Missing dates and proof signals are neutral.

(a11-typed-link-expansion)=
## A11 — Typed link expansion

`graph_retrieval.expand_typed_links` adapts the actual merge computation in
[Hindsight link expansion][typed]: `tanh(0.5 * shared_entity_count)` plus maximum
semantic weight plus maximum causal weight. It considers both edge directions,
filters to required `allowed_ids`, caps each entity's ordered member list, and
returns separate contributions. Use it for evidence neighborhoods where link
kinds provide distinct signals.

This follows the source's Python merge, which sums raw maximum causal weights;
it does not adopt the different causal-offset description in that file's opening
comment. Authorization, entity membership, link generation, and edge weights
are supplied by the host. It is one expansion step, not a graph traversal engine.

(a12-graph-distance-and-episode-mention-ranking)=
## A12 — Graph-distance and episode-mention ranking

`graph_retrieval.rank_graph_distances` and `rank_episode_mentions` are explicit
adaptations of [Graphiti's search rerankers][graphiti]. Distance ranking uses
caller-supplied nonnegative distances, reciprocal score, explicit center score,
and zero for unreachable/missing nodes. Mari does not pretend Graphiti's
adjacency query calculates all shortest paths.

Episode ranking defaults to descending mention count, with an ascending option;
missing counts sort last. This deliberately differs from the inspected upstream
ascending frequency sort. Choose distance for locality and episode count for
repetition/popularity, then evaluate which direction suits the workload.

(a13-source-preserving-surprisal-selection)=
## A13 — Source-preserving surprisal selection

`compression.select_surprising_words` adapts [LightMem's entropy compressor][lightmem].
The caller supplies observed-token probabilities, token spans, and word spans.
Word scores aggregate `-log2(probability)` by mean or first token. The top
`max(1, floor(words * fraction))` words are returned in source order with original
spans and scores; an empty input returns empty output.

Use it for inexpensive extractive compression with an external language model.
The host must align next-token probabilities correctly. Explicit spans replace
upstream tokenizer-specific grouping; cross-boundary tokens contribute to every
overlapping word. The joined text is a selection, not a grammatical summary.
The implementation scans token spans per word and does not load Torch/models.

(a14-byte-stream-fastcdc)=
## A14 — Byte-stream FastCDC

`compression.fastcdc_chunks` ports [tigerwill90/fastcdc's byte boundaries][fastcdc],
including its gear table, masks, normalization center, integer overflow, and
minimum/average/maximum size conventions. It follows the project's variant of
[Xia et al., FastCDC (USENIX ATC 2016)](https://www.usenix.org/system/files/conference/atc16/atc16-paper-xia.pdf).
Returned `ByteChunk` values own their bytes and include stream offsets.

Use it for content-defined deduplication of byte streams. Boundaries do not
depend on binary reader short-read patterns. Work is linear in bytes and buffered
memory is proportional to maximum chunk size; only the last chunk may be below
minimum. Blocking `read(size)` must return bytes; an empty read means EOF and
errors propagate. These are byte offsets, not character/token boundaries. Other
FastCDC variants can disagree. The port retains the project's MIT notice and
has a fixture generated by its unmodified Go source.

(a15-raw-heat-lfu-and-promotion)=
## A15 — Raw heat, LFU, and promotion

`memory.memory_heat`, `lfu_evictions`, and `heat_promotions` adapt
[MemoryOS's heat and capacity policies][heat]. Raw heat is
`alpha*visits + beta*interactions + gamma*exp(-age_hours/tau_hours)`;
LFU chooses lowest access count; promotion chooses strictly above-threshold
heat, hottest first. Stable insertion order resolves ties.

Use them independently for admission, retention, or tiering experiments. The host
supplies counts/age, applies returned IDs, and defines capacity. Protection can
make eviction infeasible, which raises explicitly. These functions do not copy
MemoryOS's storage or conversation workflow. Unlike timestamp-parsing upstream
fallbacks, invalid ages/parameters fail validation.

(a16-learned-blocking-and-active-pair-acquisition)=
## A16 — Learned blocking and active pair acquisition

`linkage.learn_blocking` adapts [Dedupe's bounded set-cover search][blocking].
Caller predicates expose labeled-match coverage and comparison cost. The search
minimizes the **sum** of selected predicate costs while reaching
`floor(recall * number_of_matches)` coverage. It returns selected predicate names,
coverage, cost, feasibility, search count, and whether search completed.

Use it to learn a disjunction of existing predicates before expensive pair
scoring. Predicate construction, compound predicates, training labels, and the
matcher remain external. Search is exponential in the worst case and bounded
by `max_states`; unfinished search can have no feasible incumbent even when a
solution exists. Overlapping comparison costs are counted repeatedly.

`acquire_disagreement` follows [Dedupe's matcher/blocker acquisition policy][acquire]:
prioritize uncovered likely matches, otherwise spread acquisition across covered
probabilities, otherwise sample disagreement. Mari uses a single seeded RNG and
adds uniform fallback for all-zero weights; it does not promise the identical
upstream random sequence.

(a17-entity-clustering-and-matching-choices)=
## A17 — Entity clustering and matching choices

`linkage.centroid_clusters`, `greedy_matching`, and `gazette_matching` adapt
[Dedupe's matching alternatives][linkage]. Centroid linkage uses SciPy over
`1-score` distances, missing pair distance 1, connected components, and
per-record `1 - RMS(within-cluster distances)` confidence. Singleton outputs are
omitted; isolated pairs require score strictly above threshold.

Use clustering for same-entity groups, greedy matching for one-to-one bipartite
links, or gazette matching for top matches per left record with reusable right
records. None guarantees globally optimal assignment. Centroid distances need
not be Euclidean and linkage can invert, as in the source's chosen method.
Clustering takes quadratic memory per component; oversized components raise
instead of upstream recursive rethresholding. Repeated undirected pair scores
are merged by maximum; greedy ties retain input order.

(a18-neighborhood-memory-evolution)=
## A18 — Neighborhood memory evolution

`memory.evolve_neighborhood` adapts [A-MEM's strengthen/update-neighbor actions][amem]
through a model-agnostic proposal callback. `NoteUpdate` explicitly addresses
note ID and expected revision and may change context/tags or add links. The
result contains immutable before/after notes with incremented revisions.

Use it when adding a memory should revise its neighborhood. Duplicate targets,
stale revisions, self links, and links outside the supplied neighborhood fail the
whole plan. This replaces upstream positional neighbor updates and in-place
mutation with explicit identities. The host must atomically compare-and-swap
revisions when committing; a generated plan does not reserve those revisions.

(a19-feedback-and-skill-deduplication)=
## A19 — Feedback and skill deduplication

`memory.reduce_skill_feedback` adapts [ACE's skill feedback and dedup operations][ace].
Helpful/harmful/neutral feedback increments counters and preserves provenance;
explicit keep/update/delete/merge decisions alter an immutable snapshot. Merge
sums source counters, unions provenance, and tombstones sources.

Use it for a host-controlled playbook learning loop. Persist `applied_events`
with the returned snapshot to make feedback replay idempotent. Dedup decisions
must be committed once; they are ordered operations, not replayable events.
Model evaluation, decision generation, transactions, and eventual garbage
collection remain caller choices. Deleted records cannot receive new feedback
or be reused in another merge.

(a20-graph-structural-alternatives)=
## A20 — Graph structural alternatives

`graphs.condense_graph`, `transitive_reduction_edges`, and `cohesive_subgraph`
expose [NetworkX structural algorithms][structure]. Condensation returns strongly
connected components plus their DAG. Transitive reduction removes redundant DAG
edges while retaining reachability and surviving original weights. Cohesion
selects topological k-core or k-truss nodes; weights do not change membership.

Use SCCs for cycles, reduction for dependency explanations, and cores/trusses for
dense neighborhoods. Reduce only DAGs; condense first when cycles exist. Parallel
edges require explicit caller aggregation, and cohesion rejects self loops.
These algorithms do not impose application graph semantics.

(a21-common-space-union-ranking)=
## A21 — Common-space union ranking

`graph_retrieval.rank_candidate_union` adapts [haiku.rag's search union ordering][union].
Select either cosine scoring across a named common embedding space or scores
from a reranker applied to the complete union. Identity is `(source, item_id)`;
a required allowed-key set filters candidates before scoring.

Use this when searching several collections with compatible vectors or a shared
reranker. The cosine path validates dimensions, space identity, and finite
values; zero vectors score zero. The reranker path requires supplied scores for
every allowed candidate. Duplicate keys are rejected and deterministic ties
retain within-source rank then source arrival order. This does not calibrate
unrelated collection scores or independently normalized reranker batches.

## Validation and limits

Run the new tests with `pytest -q tests/test_algorithm_*.py`. The suite includes
rank_bm25-generated score fixtures, a Go-generated FastCDC boundary fixture,
exhaustive small blocking comparisons, lazy/naive equivalence on random coverage,
a PCST bridge case, native graph checks, and callback/scope/revision edge cases.
Optional-solver tests skip when dependencies are absent; install the extra to
exercise them. CI includes a separate solver job as well as the base test matrix.
Local native validation used NetworkX 3.6.1, pcst-fast 1.0.10,
graspologic-native 1.3.1, and SciPy 1.18.1 on Python 3.13.

These checks establish the stated computation and interface behaviors on small
fixtures. They do not establish retrieval quality, extraction quality, native
cross-version reproducibility, or large-scale throughput. Model callbacks and
source data require workload-specific evaluation. Source citations acknowledge
provenance; adapted interfaces and policies are described above rather than
presented as complete upstream systems.

[bm25]: https://github.com/dorianbrown/rank_bm25/blob/47aa3ddf8dc1ebeb7ef4e65f2b4536af44594099/rank_bm25.py
[submodlib]: https://github.com/decile-team/submodlib/tree/72ae33a1ead9761e7240c2e095873047339ada7c/submodlib/functions
[greedy]: https://github.com/decile-team/submodlib/tree/72ae33a1ead9761e7240c2e095873047339ada7c/cpp/optimizers
[pcst]: https://github.com/fraenkel-lab/pcst_fast/blob/25ab31a245b2278848b5a8814924cdb3039b4279/README.md
[louvain]: https://github.com/networkx/networkx/blob/0db8227000872d7a9f6ce84c54ba1e5e99429122/networkx/algorithms/community/louvain.py
[leiden]: https://github.com/microsoft/graphrag/blob/f40e9a26ce62ba0b3fef8837d24aafdcc6e6c704/packages/graphrag/graphrag/graphs/hierarchical_leiden.py
[hippo]: https://github.com/OSU-NLP-Group/HippoRAG/blob/eb0568d6f75bac037b37e7404603462db60ffac2/src/hipporag/HippoRAG.py
[drift]: https://github.com/microsoft/graphrag/tree/f40e9a26ce62ba0b3fef8837d24aafdcc6e6c704/packages/graphrag/graphrag/query/structured_search/drift_search
[polling]: https://github.com/HKUDS/LightRAG/blob/c1248646e4eda4d89054926af2e094730daf23fe/lightrag/utils.py
[glean]: https://github.com/HKUDS/LightRAG/blob/c1248646e4eda4d89054926af2e094730daf23fe/lightrag/operate.py
[temporal]: https://github.com/vectorize-io/hindsight/blob/614bfc96dfde3138bed109113358013f975d8c40/hindsight-api-slim/hindsight_api/engine/search/reranking.py
[typed]: https://github.com/vectorize-io/hindsight/blob/614bfc96dfde3138bed109113358013f975d8c40/hindsight-api-slim/hindsight_api/engine/search/link_expansion_retrieval.py
[graphiti]: https://github.com/getzep/graphiti/blob/11538f6d45561bcce9a4400b374fb2dc533dccb6/graphiti_core/search/search_utils.py
[lightmem]: https://github.com/zjunlp/LightMem/blob/aa1c484cc6fd964c8ea1af897e36a0c3ba06d7db/src/lightmem/factory/pre_compressor/entropy_compress.py
[fastcdc]: https://github.com/tigerwill90/fastcdc/blob/086f08a7b4681e178e2f24d73a2d62edf2a1135f/chunker.go
[heat]: https://github.com/BAI-LAB/MemoryOS/blob/587ed7755c7aed179965792830ff1b5ad9a6fa92/memoryos-chromadb/mid_term.py
[blocking]: https://github.com/dedupeio/dedupe/blob/3f61e79102910bd355e920a2df7e44c14c9cb247/dedupe/branch_and_bound.py
[acquire]: https://github.com/dedupeio/dedupe/blob/3f61e79102910bd355e920a2df7e44c14c9cb247/dedupe/labeler.py
[linkage]: https://github.com/dedupeio/dedupe/blob/3f61e79102910bd355e920a2df7e44c14c9cb247/dedupe/clustering.py
[amem]: https://github.com/agiresearch/A-mem/blob/ceffb860f0712bbae97b184d440df62bc910ca8d/agentic_memory/memory_system.py
[ace]: https://github.com/kayba-ai/agentic-context-engine/blob/321d430e520f369315bad512cd2d90f1fa14a596/ace/core/skillbook.py
[structure]: https://github.com/networkx/networkx/tree/0db8227000872d7a9f6ce84c54ba1e5e99429122/networkx/algorithms
[union]: https://github.com/ggozad/haiku.rag/blob/cf674b93ce50a742371addbfb8f9aa0bfa733ae7/haiku_rag_slim/haiku/rag/client/search.py

[mari-polar]: https://github.com/MariHQ/mari-kit/blob/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/retrieval/polarquant.py
[mari-fusion]: https://github.com/MariHQ/mari-kit/blob/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/retrieval/fusion.py
[mari-context]: https://github.com/MariHQ/mari-kit/blob/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/retrieval/context.py
[mari-markdown]: https://github.com/MariHQ/mari-kit/blob/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/documents/markdown.py
[mari-atoms]: https://github.com/MariHQ/mari-kit/blob/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/documents/atoms.py
[mari-links]: https://github.com/MariHQ/mari-kit/blob/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/knowledge/links.py
[mari-admission]: https://github.com/MariHQ/mari-kit/blob/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/knowledge/admission.py
[mari-governance]: https://github.com/MariHQ/mari-kit/blob/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/governance/__init__.py
[mari-provenance]: https://github.com/MariHQ/mari-kit/blob/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/graph/provenance.py
[mari-diagnostics]: https://github.com/MariHQ/mari-kit/blob/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/graph/diagnostics.py
[mari-topics]: https://github.com/MariHQ/mari-kit/blob/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/conversation_topics.py
[mari-dependencies]: https://github.com/MariHQ/mari-kit/blob/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/dependencies.py
[mari-grouping]: https://github.com/MariHQ/mari-kit/blob/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/grouping.py
[mari-aggregates]: https://github.com/MariHQ/mari-kit/blob/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/aggregates.py
[mari-freshness]: https://github.com/MariHQ/mari-kit/blob/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/knowledge/freshness.py
[mari-sync]: https://github.com/MariHQ/mari-kit/blob/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/sync/planning.py
[mari-assertions]: https://github.com/MariHQ/mari-kit/blob/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/knowledge/assertions.py
[mari-decisions]: https://github.com/MariHQ/mari-kit/blob/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/retrieval/decisions.py
[mari-metrics]: https://github.com/MariHQ/mari-kit/blob/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/evaluation/metrics.py
[mari-graph-eval]: https://github.com/MariHQ/mari-kit/blob/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/evaluation/graph.py
[mari-statistics]: https://github.com/MariHQ/mari-kit/blob/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/evaluation/statistics.py
[mari-gates]: https://github.com/MariHQ/mari-kit/blob/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/evaluation/gates.py
[mari-package]: https://github.com/MariHQ/mari-kit/tree/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit
[mari-connectors]: https://github.com/MariHQ/mari-kit/tree/8f6c1bc907b76b4cce054010485f3ffa6a1a15bd/src/mari_kit/connectors
