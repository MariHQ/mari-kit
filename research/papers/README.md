# Paper implementation queue

PDFs enter `pending/`. A PDF moves to `completed/` only after its reusable
algorithm boundary has code, public exports, tests, and documentation.

| arXiv | Paper | Mari implementation | Tests | State |
|---|---|---|---|---|
| [2402.03367](https://arxiv.org/abs/2402.03367) | RAG-Fusion | `retrieval.reciprocal_rank_fusion` | `test_retrieval_algorithms.py` | completed |
| [2405.14831](https://arxiv.org/abs/2405.14831) | HippoRAG | `retrieval.personalized_pagerank`, `project_graph_scores` | `test_retrieval_algorithms.py` | completed |
| [2504.19413](https://arxiv.org/abs/2504.19413) | Mem0 | `knowledge.plan_memory_mutations`, `apply_memory_mutations` | `test_memory_algorithms.py` | completed |
| [2510.18866](https://arxiv.org/abs/2510.18866) | LightMem | `knowledge.hybrid_topic_segments` | `test_memory_algorithms.py` | completed |
| [2212.10496](https://arxiv.org/abs/2212.10496) | HyDE | `retrieval.hypothetical_document_embedding` | `test_research_extensions.py` | completed |
| [2401.18059](https://arxiv.org/abs/2401.18059) | RAPTOR | `retrieval.build_summary_tree` | `test_research_extensions.py` | completed |
| [2310.11511](https://arxiv.org/abs/2310.11511) | Self-RAG | `verification.score_self_rag_candidate` | `test_research_extensions.py` | completed |
| [2401.15884](https://arxiv.org/abs/2401.15884) | CRAG | `retrieval.plan_corrective_retrieval` | `test_research_extensions.py` | completed |
| [2305.06983](https://arxiv.org/abs/2305.06983) | FLARE | `retrieval.plan_active_retrieval` | `test_research_extensions.py` | completed |
| [2502.12110](https://arxiv.org/abs/2502.12110) | A-MEM | `knowledge.plan_note_evolution` | `test_research_extensions.py` | completed |
| [2304.03442](https://arxiv.org/abs/2304.03442) | Generative Agents | `knowledge.rank_salient_memories` | `test_research_extensions.py` | completed |
| [2310.05029](https://arxiv.org/abs/2310.05029) | MemWalker | `retrieval.walk_summary_tree` | `test_research_extensions.py` | completed |
| [2311.09210](https://arxiv.org/abs/2311.09210) | Chain-of-Note | `verification.decide_from_evidence_notes` | `test_research_extensions.py` | completed |
| [2310.04408](https://arxiv.org/abs/2310.04408) | RECOMP | `retrieval.selective_compression` | `test_research_extensions.py` | completed |

Implementation notes and runnable examples are in
[`docs/research-algorithms.md`](../../docs/research-algorithms.md) and
[`docs/ten-paper-extensions.md`](../../docs/ten-paper-extensions.md).
