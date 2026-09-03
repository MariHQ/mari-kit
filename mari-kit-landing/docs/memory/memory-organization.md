[]{#memory-organization}[Current]{.current-label}

# Memory organization and evidence notes

## At a glance

| Organization policy | LongMemEval observation | Trade-off |
|---|---|---|
| Recency + importance + BM25 relevance | Evidence recall@10 `0.953`; complete recall `0.906` | Relevance dominates under the measured `0.15/0.15/0.70` weights |
| A-MEM link thresholds | Precision `0.436`; recall `0.944`; F1 `0.597` | Broad linking finds evidence but creates many weak links |
| Chain-of-Note source choice | Gold-judgment component check only | Replace oracle judgments with a measured classifier before claiming answer quality |

:::{collapse} Actual LongMemEval retrieval differences

| Question ID | Type | Gold sessions | Gold ranks | Recall-all@5 |
|---|---|---:|---|---:|
| `e47becba` | Single-session user | 1 | `2` | 1.0 |
| `6d550036` | Multi-session | 4 | `4`, `8`, `>10`, `>10` | 0.0 |

The second case retrieves one supporting session near the top but misses the complete evidence set. `Recall-any` would hide that structural failure.
:::



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
