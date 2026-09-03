[]{#memory-organization}[Current]{.current-label}

# Memory organization and evidence notes

## Evaluation

Five conformance cases exercise note-link/evolution thresholds, normalized recency-importance-relevance components, Chain-of-Note decisions, and inconsistency rejection. The public LongMemEval-S run measures the downstream lexical session-retrieval boundary over 470 questions: `0.8298` Recall-all@5 and `0.9021` Recall-all@10. A-MEM, Generative Agents, and Chain-of-Note task-level gains have not been reproduced.

```console
$ pytest -q tests/test_research_extensions.py -k 'AgenticMemory or ReflectionAndEvidenceNote'
5 passed
$ python benchmarks/run_public.py longmemeval
```


These functions link related notes, rank memories for recall, and decide whether retrieved evidence can support an answer.

## How it works

Note evolution applies a link threshold and a stricter metadata-evolution threshold to caller-supplied similarities. Salience exponentially decays recency, min-max normalizes recency, importance, and relevance over the candidate set, then returns every weighted contribution. Evidence-note decisions validate per-document relevance and answer support before choosing retrieved evidence, explicitly allowed parametric knowledge, or `unknown`.

::: source-block
**Papers**

[A-MEM: dynamic note evolution](https://arxiv.org/abs/2502.12110){.paper}[Generative Agents: recency, importance, and relevance](https://arxiv.org/abs/2304.03442){.paper}[Chain-of-Note: sequential evidence decisions](https://arxiv.org/abs/2311.09210){.paper}
:::

```{code-block} python
:caption: memory_evidence.py · current

from mari_components.knowledge import (
    MemorySignal, plan_note_evolution, rank_salient_memories,
)
from mari_components.verification import (
    EvidenceNote, decide_from_evidence_notes,
)

evolution = plan_note_evolution(new_note.id, similarity_by_note_id,
    link_threshold=0.72, evolution_threshold=0.91)
salient = rank_salient_memories([
    MemorySignal(memory_id=m.id, hours_since_access=hours_since(m.last_accessed),
        importance=importance(m), relevance=relevance(query, m)) for m in memories
], recency_decay=0.995, limit=20)
decision = decide_from_evidence_notes([
    EvidenceNote(document_id=n.document_id, relevant=n.relevant,
        supports_answer=n.supports_answer) for n in model_notes
])
```
