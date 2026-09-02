# Ten paper-derived knowledge-system extensions

Mari implements the deterministic, reusable boundary from each paper. It does
not bundle language models, embedding models, training loops, web search,
vector databases, or persistence. Callers produce model-dependent signals;
Mari validates them and returns immutable, auditable results.

## Coverage

| Paper | Public API | Implemented subset | Application supplies |
|---|---|---|---|
| [HyDE](https://arxiv.org/abs/2212.10496) | `hypothetical_document_embedding` | Weighted centroid and L2 normalization of hypothetical-document vectors | Hypothetical text generation, encoder, vector search |
| [RAPTOR](https://arxiv.org/abs/2401.18059) | `build_summary_tree` | Validated recursive cluster/summarize tree construction with stable content-derived parent IDs | Clustering and summarization callbacks |
| [Self-RAG](https://arxiv.org/abs/2310.11511) | `score_self_rag_candidate` | Weighted inference-time combination of generation, relevance, support, and utility probabilities; retrieval threshold | Reflection-token model and candidate generation |
| [CRAG](https://arxiv.org/abs/2401.15884) | `plan_corrective_retrieval` | Correct, ambiguous, and incorrect action routing from document confidence | Retrieval evaluator and external retrieval implementation |
| [FLARE](https://arxiv.org/abs/2305.06983) | `plan_active_retrieval` | Low-confidence trigger detection and masking of uncertain future tokens | Future-sentence prediction, token probabilities, retrieval, regeneration |
| [A-MEM](https://arxiv.org/abs/2502.12110) | `plan_note_evolution` | Separate thresholds for note linking and stronger contextual-evolution candidates | Note generation, similarity, metadata patch generation, persistence |
| [Generative Agents](https://arxiv.org/abs/2304.03442) | `rank_salient_memories` | Exponential recency, min-max normalization, and weighted recency/importance/relevance ranking | Importance and relevance judgments, context packing |
| [MemWalker](https://arxiv.org/abs/2310.05029) | `walk_summary_tree` | Bounded relevance-guided summary-tree traversal with visit trace | Query-to-node scorer and stopping policy |
| [Chain-of-Note](https://arxiv.org/abs/2311.09210) | `decide_from_evidence_notes` | Retrieved, parametric, or unknown answer-source decision from sequential notes | Note generation and final answer generation |
| [RECOMP](https://arxiv.org/abs/2310.04408) | `selective_compression` | Budgeted extractive selection over externally scored sentences, source-order rendering, and empty augmentation | Sentence splitting, learned scores, token counts |

## Retrieval construction

### HyDE query vectors

```python
from mari_components.retrieval import hypothetical_document_embedding

hypotheses = generate_hypothetical_documents(query, samples=4)
vectors = [document_encoder(text) for text in hypotheses]
query_vector = hypothetical_document_embedding(vectors)
hits = vector_index.search(query_vector)
```

HyDE warns that generated documents may contain false details. Mari returns a
retrieval vector, never a factual artifact. The returned vector is always
one-dimensional, finite, non-zero, L2-normalized `float32`.

### RAPTOR construction and MemWalker traversal

```python
from mari_components.retrieval import build_summary_tree, walk_summary_tree

tree = build_summary_tree(
    section_text_by_id,
    cluster=lambda nodes, level: cluster_embeddings(nodes, level=level),
    summarize=lambda children, level: model_summary(children, level=level),
)

walk = walk_summary_tree(
    tree,
    score=lambda node: query_similarity(query, node.text),
    branch_factor=2,
    max_visits=24,
)
source_sections = document_store.get_many(walk.leaf_ids)
audit(walk.visited, walk.exhausted)
```

Every clustering round must partition the current roots exactly once and reduce
their count. This catches lost nodes, duplicates, and non-progressing callback
implementations. `walk_summary_tree` expands only the highest-scoring children,
uses stable ID tie-breaking, and reports whether the frontier was exhausted.

## Adaptive and corrective retrieval

### CRAG action routing

```python
from mari_components.retrieval import CorrectiveAction, plan_corrective_retrieval

plan = plan_corrective_retrieval(
    evaluator.score(query, retrieved_documents),
    lower_threshold=-0.8,
    upper_threshold=0.6,
)

match plan.action:
    case CorrectiveAction.USE_RETRIEVED:
        context = refine(retrieved_documents)
    case CorrectiveAction.COMBINE_WITH_EXTERNAL:
        context = refine((*retrieved_documents, *external_search(query)))
    case CorrectiveAction.REPLACE_WITH_EXTERNAL:
        context = refine(external_search(query))
```

Mari accepts any finite evaluator scale as long as its thresholds use the same
scale. It uses the best document score: at least one score at or above the upper
threshold is correct; all scores at or below the lower threshold are incorrect;
the remainder is ambiguous.

### FLARE retrieval triggers

```python
from mari_components.retrieval import plan_active_retrieval

prediction = predict_next_sentence(prefix, return_token_probabilities=True)
request = plan_active_retrieval(
    prediction.tokens,
    prediction.probabilities,
    threshold=0.2,
)
if request is not None:
    evidence = retrieve(request.query)
    sentence = regenerate(prefix, evidence=evidence)
```

The result records all low-confidence positions and the minimum probability.
Mari removes uncertain tokens from the retrieval query; it does not decide how
to generate or splice the replacement sentence.

### Self-RAG inference scoring

```python
from mari_components.verification import score_self_rag_candidate

score = score_self_rag_candidate(
    generation_probability=signals.generation,
    retrieve_probability=signals.retrieve,
    relevance_probability=signals.relevant,
    support_probability=signals.supported,
    utility=signals.utility,
    support_weight=2.0,
)
if score.retrieve:
    retrieve_for_next_segment()
ranker.add(candidate, score=score.score, trace=score)
```

Every probability is validated in `[0, 1]`. The result retains the weighted
relevance, support, and utility contributions rather than returning only their
sum.

## Memory organization

### A-MEM note evolution

```python
from mari_components.knowledge import plan_note_evolution

plan = plan_note_evolution(
    new_note.id,
    similarities_to_existing_notes,
    link_threshold=0.72,
    evolution_threshold=0.91,
    limit=12,
)
links.propose(new_note.id, plan.link_ids)
for note_id in plan.evolution_ids:
    metadata_reviews.propose(note_id, caused_by=new_note.id)
```

Evolution candidates are always a subset of links. Mari does not let similarity
rewrite historical note text; an application may propose versioned metadata
patches and review them.

### Generative Agents salience

```python
from mari_components.knowledge import MemorySignal, rank_salient_memories

hits = rank_salient_memories(
    [
        MemorySignal(
            memory_id=memory.id,
            hours_since_access=hours_since(memory.last_accessed),
            importance=importance_model(memory),
            relevance=cosine(query_vector, memory.vector),
        )
        for memory in memories
    ],
    recency_decay=0.995,
    limit=20,
)
```

Mari applies the paper's exponential recency and min-max normalizes all three
components within the candidate set. Constant components normalize to `1.0`, so
they do not introduce arbitrary ordering. Equal totals break by memory ID.

## Evidence reading and compression

### Chain-of-Note answerability

```python
from mari_components.verification import EvidenceNote, decide_from_evidence_notes

notes = tuple(
    EvidenceNote(
        document_id=document.id,
        relevant=model_note.relevant,
        supports_answer=model_note.supports_answer,
    )
    for document, model_note in read_documents_sequentially(documents)
)
decision = decide_from_evidence_notes(
    notes,
    parametric_knowledge_available=validated_closed_book_answer is not None,
)
```

The decision prefers supporting retrieved evidence, then explicitly available
parametric knowledge, then `UNKNOWN`. A note cannot support an answer while also
being marked irrelevant.

### RECOMP extractive execution

```python
from mari_components.retrieval import CompressionSentence, selective_compression

compressed = selective_compression(
    [
        CompressionSentence(
            sentence_id=sentence.id,
            text=sentence.text,
            token_count=tokenizer.count(sentence.text),
            relevance=compressor.score(query, sentence.text),
        )
        for sentence in retrieved_sentences
    ],
    token_budget=600,
    relevance_threshold=0.4,
)
```

Selection is by relevance per token with stable ties, then selected sentences
are restored to source order. If nothing clears the threshold and budget, the
result contains an empty string, making selective non-augmentation explicit.

## Boundaries and claims

These functions are paper-derived components, not reproductions of full paper
systems. In particular:

- Paper-reported quality does not transfer automatically to caller-supplied
  models, corpora, thresholds, or backends.
- Thresholds must be calibrated on application validation data.
- Model-produced relevance, support, importance, and utility values are signals,
  not probabilities of truth unless the application establishes calibration.
- Authorization filtering must happen before any algorithm receives candidates.
- Traces should be retained with model, embedding, corpus, and configuration
  identities so evaluations can be reproduced.
