# Research-shelf coverage audit

Audit date: 2026-09-03. The source shelf is `/Users/henneberger/memory`.
“Covered” means Mari has the relevant framework-neutral primitive; it does not
mean upstream code was vendored or that Mari reproduces an upstream product.

## Added in this pass

| Reference | Mari primitive |
|---|---|
| `experience-reasoning-bank` | Contrastive success/failure pattern associations with source-run IDs and uncertainty; evidence-bound strategy and pitfall candidates |
| `experience-plugmem` | Applicability and limitation fields; context use, token utilization, and caller-run ablation deltas |
| `trace-otel-genai` | Content-redacting OTLP GenAI normalization, schema identity, trace links, explicit unknown outcomes, and structural integrity reports |
| Meta organizational second brain | Knowledge-use manifests, correction root-cause diagnosis, exact minimal edit proposals, dependency symmetry/cycle checks, and targeted/regression evaluation values |
| Google intent decomposition | Caller-vector intent clustering, ambiguity, novelty, and temporal drift summaries |
| AWS episodic memory | Evidence-bound turn assessments, caller-bound episodes, and cross-episode reflection candidates |
| Anthropic evaluation guidance | Paired bootstrap intervals, categorical slices, reviewer reliability, pass@k, and pass^k summaries |
| Contextual retrieval and late chunking | Context-prefixed indexing representations that preserve original spans; token-span pooling |
| Google sufficient-context work | Explicit requirements, supported/contradicted/missing/ambiguous assessment, and bounded retrieval-gap queries |

## Shelf ideas already represented

| Shelf area | Existing Mari coverage |
|---|---|
| Mem0, Memoripy, A-MEM, MemoryOS, LightMem | Admission, immutable revisions, mutation plans, topic segmentation, salience, promotion, and consolidation |
| Graphiti, GraphRAG, LightRAG, HippoRAG | Bitemporal facts, communities, graph retrieval, Personalized PageRank, subgraph selection, and evidence projection |
| Hindsight, MemSearch, Supermemory | Multi-arm fusion, two-stage hydration, context envelopes, lifecycle decisions, and retrieval traces |
| Codebase-memory, DSP, LinkML, pySHACL | Code structure, dependency/lineage traversal, semantic schemas, constraints, and compilation inputs |
| Semiont, portable-memory, Apertomemory | Append-only projections, portable bundles, checksums, signatures, and import validation |
| Connector and parser references | Polling and streaming protocols, canonical documents, sync planning, structured document IR, and positioned parser diagnostics |

## Implemented after the initial audit

| Primitive | Current implementation | Boundary |
|---|---|---|
| Knowledge observation ledger | Exact retrieved, shown, cited, and used stage records plus ordering diagnostics | Immutable records only; no runtime hooks or store |
| Derivation-loop detection | Missing-input, cycle, and derived-as-independent reports over exact revisions | Caller decides rejection |
| Conditional disclosure predicate | Inspectable `exists`, equality, inequality, and membership conditions | Never an ACL substitute |
| Knowledge changeset validation | Multi-document preconditions, overlap checks, previews, proposed hashes, and inverse edits | Transactions and rollback remain store-owned |
| Progressive disclosure manifest | Validated index → summary → section → source expansion with token accounting | No UI, retrieval model, or generation pipeline |

These are derived from narrow reusable ideas in `letta-code`, `memoripy`,
`nocturne_memory`, `pi-llm-wiki`, and related shelf projects. None imports an
upstream framework, runtime, or storage design.

## Intentionally excluded

Agent loops, reflection schedulers, model clients, hosted judges, training or
reinforcement-learning systems, canonical ontologies, database engines,
dashboards, and automatic graph construction remain outside Mari. They are
product, model, or persistence choices rather than knowledge-management
primitives.
