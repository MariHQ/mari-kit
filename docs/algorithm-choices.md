# Algorithm choices

Mari Kit is a collection of independently selectable algorithms. Similar methods
coexist because workloads differ. These additions use plain IDs, matrices,
source spans, and callbacks; none requires Mari's atom schema, a particular
product, or a data store. Import the family you need from
`mari_components.algorithms` rather than adopting an entire pipeline.

This catalog implements all 21 candidate groups from the September 5, 2026
local-shelf reassessment. Sources below link to the **inspected project commits**,
not moving default branches. “Formula” describes the cited computation;
“adapter” invokes an optional implementation; “adaptation” changes the surrounding
policy or interface. These labels do not claim to reproduce a whole research
system or its benchmark results.

## Installation and executable example

```console
pip install mari-components
python -m examples.algorithm_choices_demo
# Optional native graph and centroid-linkage operations:
pip install 'mari-components[algorithm-solvers]'
```

The example command runs from a repository checkout. Core algorithms need only
NumPy. The optional extra installs NetworkX, pcst-fast, graspologic-native, and
SciPy; imports are deferred until their individual operation is called. Hosts
may install only the particular solver needed. Missing dependencies raise an
ImportError naming the extra. Native binary availability depends on platform.

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

## A04 — Prize-collecting forest solver

`graphs.prize_collecting_forest` adapts [pcst_fast][pcst] to caller node prizes
and edge **costs**. It returns original IDs/edges and prize/cost totals. A rooted
call fixes its required root; an unrooted call can request multiple clusters.
Choose it when valuable evidence requires intermediate connectors, including
zero-prize nodes. This is the native approximation, not an exact optimal solver.
The existing greedy selector remains useful as a different low-overhead choice.
Optional `allowed_nodes` induces the input graph before solving.

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
