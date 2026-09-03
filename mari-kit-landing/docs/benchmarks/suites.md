# Algorithm benchmark suites

Each algorithm has a named suite in `benchmarks/suites.json`. A repository test fails when a completed paper has no suite, a suite names an unknown corpus, or suite IDs collide. The JSON file is the machine-readable source; this page explains what each suite measures.

## Indexes and ranking

### Dense exact search

**Benchmark:** BEIR and LoTTE; nDCG@10, Recall@100, p95 latency, and index bytes.

`DenseFlatIndex` computes exact cosine, dot-product, or Euclidean rankings. It is the recall oracle for approximate indexes. [BEIR](https://arxiv.org/abs/2104.08663){.paper} provides heterogeneous zero-shot retrieval tasks; [ColBERT](https://arxiv.org/abs/2004.12832){.paper} motivates token-level late interaction.

### HNSW

**Benchmark:** BEIR; Recall@k against `DenseFlatIndex`, p95 latency, and index bytes.

`HNSWIndex` builds deterministic proximity layers and performs graph traversal over authorized candidates. The benchmark sweeps construction degree, search effort, and `k`. [Efficient and robust approximate nearest neighbor search using HNSW](https://doi.org/10.1109/TPAMI.2018.2889473){.paper}

### IVF-PQ

**Benchmark:** BEIR; Recall@k against exact search, p95 latency, and bytes per vector.

`IVFPQIndex` learns coarse cells, encodes residual sub-vectors with product quantization, probes selected cells, and ranks approximate reconstructed distances. The suite sweeps probe count, subquantizers, and codebook size. [Product quantization for nearest neighbor search](https://doi.org/10.1109/TPAMI.2010.57){.paper}

### BM25 and learned sparse retrieval

**Benchmark:** BEIR and LoTTE; nDCG@10, Recall@100, latency, and nonzero terms.

`BM25Index` uses Robertson–Walker inverse document frequency plus saturating term frequency and length normalization. `SparseVectorIndex` ranks caller-produced term weights, keeping model inference outside the index. [The Probabilistic Relevance Framework: BM25 and Beyond](https://doi.org/10.1561/1500000019){.paper} [SPLADE](https://arxiv.org/abs/2107.05720){.paper}

### Multi-vector and fused retrieval

**Benchmark:** BEIR and LoTTE; exact MaxSim agreement, Recall@k, nDCG@10, and fusion gain.

MUVERA converts multi-vector MaxSim search into fixed-dimensional encodings; RAG-Fusion combines independently ranked query variants by reciprocal rank. [MUVERA](https://arxiv.org/abs/2405.19504){.paper} [RAG-Fusion](https://arxiv.org/abs/2402.03367){.paper}

## Retrieval control and context

### Hypothetical, corrective, and active retrieval

**Benchmark:** BEIR, FEVER, QASC, QASPER, and FreshQA; retrieval gain, routing accuracy, trigger F1, evidence F1, answer accuracy, and retrieval calls.

HyDE embeds a generated hypothetical answer rather than the short query. CRAG maps retrieval confidence to accept, supplement, or replace plans. FLARE triggers retrieval at low-confidence generation positions. Model calls are injected; Mari evaluates their deterministic planning boundaries. [HyDE](https://arxiv.org/abs/2212.10496){.paper} [CRAG](https://arxiv.org/abs/2401.15884){.paper} [FLARE](https://arxiv.org/abs/2305.06983){.paper}

### Summary trees and evidence notes

**Benchmark:** QASPER and LongBench; answer F1, leaf recall, tree coverage, nodes visited, evidence recall, and compression ratio.

RAPTOR recursively clusters and summarizes text; MemWalker traverses such a hierarchy; RECOMP selects a bounded evidence representation; Chain-of-Note records source-level support before deciding whether to answer. [RAPTOR](https://arxiv.org/abs/2401.18059){.paper} [MemWalker](https://arxiv.org/abs/2310.05029){.paper} [RECOMP](https://arxiv.org/abs/2310.04408){.paper} [Chain-of-Note](https://arxiv.org/abs/2311.09210){.paper}

### Self-reflective selection and context envelopes

**Benchmark:** FEVER, QASC, LongBench, and QASPER; candidate selection, evidence density, answer F1, tokens, and ACL leakage.

Self-RAG scores relevance, support, and utility signals supplied by an evaluator. `assemble_context` first removes unauthorized and stale material, then selects whole excerpts under token and item budgets and records exclusions. [Self-RAG](https://arxiv.org/abs/2310.11511){.paper} [Lost in the Middle](https://arxiv.org/abs/2307.03172){.paper}

## Graphs, identity, and contradiction

### Multi-hop graph retrieval

**Benchmark:** QASC, KILT, and DocRED; multi-hop accuracy, passage recall, and path provenance.

HippoRAG uses personalized PageRank over entity–passage relationships, then projects node scores back to passages. [HippoRAG](https://arxiv.org/abs/2405.14831){.paper}

### Community aggregation

**Benchmark:** DocRED and KILT; modularity, community coverage, evidence recall, and answer accuracy.

`leiden_communities` performs deterministic modularity-improving local moves and refines every output community to connected components. `build_community_reports` and `map_reduce_reports` keep generation callbacks injected and bound the number of mapped reports. [Leiden](https://arxiv.org/abs/1810.08473){.paper} [GraphRAG](https://arxiv.org/abs/2404.16130){.paper}

### Temporal facts and entity resolution

**Benchmark:** LongMemEval, DocRED, and WDC Products; temporal accuracy, update fidelity, provenance recall, pair/cluster F1, pairs completeness, and reduction ratio.

Bi-temporal facts use half-open valid and transaction intervals. Entity resolution uses Fellegi–Sunter log likelihood ratios with explicit match, review, and non-match bands. [Temporal knowledge graph survey](https://arxiv.org/abs/2201.08236){.paper} [Fellegi and Sunter](https://doi.org/10.1080/01621459.1969.10501049){.paper}

### Contradiction retrieval and document consistency

**Benchmark:** ContraDoc, BEIR ArguAna; contradiction Recall@k, nDCG@10, macro-F1, localization F1, and candidate-pair reduction.

SparseCL supplies the sparse contradiction-retrieval objective. Document-level validation aggregates localized contradiction edges, semantic-equivalence exclusions, coreference-aware candidates, and document decisions. [SparseCL](https://arxiv.org/abs/2406.10746){.paper} [Document-Level Self-Contradiction Detection](https://aclanthology.org/2025.emnlp-main.67/){.paper}

## Memory and procedures

### Mutation, evolution, salience, and consolidation

**Benchmark:** LongMemEval and WikiSection; operation F1, update fidelity, stale-fact rate, link F1, boundary F1, Pk, answer accuracy, and write cost.

Mem0 supplies explicit add/update/delete/no-op mutation plans; A-MEM proposes linked note evolution; generative-agent salience combines recency, importance, and relevance; LightMem adds topic-aware segmentation and budgeted offline consolidation. [Mem0](https://arxiv.org/abs/2504.19413){.paper} [A-MEM](https://arxiv.org/abs/2502.12110){.paper} [Generative Agents](https://arxiv.org/abs/2304.03442){.paper} [LightMem](https://arxiv.org/abs/2510.18866){.paper}

### Procedures and compilation

**Benchmark:** QASC, KILT, BEIR, FEVER, and LongMemEval; task success, tool-sequence F1, groundedness, cost, objective utility, constraint violations, and held-out score.

Procedure learning extracts the stable subsequence shared by successful tool traces. Hard gates compare candidates to absolute requirements and active baselines. Compilation evaluates each unique configuration, rejects constraint violations, and ranks the feasible set. [Voyager](https://arxiv.org/abs/2305.16291){.paper} [Reflexion](https://arxiv.org/abs/2303.11366){.paper} [DSPy](https://arxiv.org/abs/2310.03714){.paper}
