[]{#adaptive-retrieval}[Current]{.current-label}

# Adaptive retrieval and compression

## Evaluation

Five deterministic cases exercise Self-RAG contribution accounting, all three CRAG routes, FLARE masking and no-retrieval behavior, and Chain-of-Note support/abstention decisions. This validates Mari's planning boundary, not the papers' model quality. FEVER, QASC, FreshQA, and QASPER task scores have not been run.

```console
$ pytest -q tests/test_research_extensions.py -k 'CorrectiveAndActiveRetrieval or ReflectionAndEvidenceNote'
5 passed
```


Retrieval can be triggered, corrected, rescored, or compressed at explicit decision points instead of running as one opaque model call.

## How it works

CRAG routing maps evaluator scores through two thresholds to use the corpus, augment it with external search, or replace it. FLARE finds low-confidence tokens in a predicted future sentence, removes those tokens, and uses the remaining text as a retrieval query before regeneration. Self-RAG combines generation, retrieval, relevance, support, and utility signals with visible weights. RECOMP selects scored sentences under a token budget, then restores their source order.

::: source-block
**Papers**

[Self-RAG: reflection-token scoring](https://arxiv.org/abs/2310.11511){.paper}[CRAG: corrective retrieval](https://arxiv.org/abs/2401.15884){.paper}[FLARE: forward-looking active retrieval](https://arxiv.org/abs/2305.06983){.paper}[RECOMP: selective compression](https://arxiv.org/abs/2310.04408){.paper}
:::

```{code-block} python
:caption: adaptive_retrieval.py · current

from mari_components.retrieval import (
    CompressionSentence, plan_active_retrieval, plan_corrective_retrieval,
    selective_compression,
)
from mari_components.verification import score_self_rag_candidate

correction = plan_corrective_retrieval(retrieval_evaluator(query, hits),
    lower_threshold=-0.8, upper_threshold=0.6)
active = plan_active_retrieval(future.tokens, future.probabilities, threshold=0.2)
reflection = score_self_rag_candidate(generation_probability=signals.generation,
    retrieve_probability=signals.retrieve, relevance_probability=signals.relevant,
    support_probability=signals.supported, utility=signals.utility)

compressed = selective_compression([
    CompressionSentence(sentence_id=s.id, text=s.text, token_count=count_tokens(s.text),
        relevance=compressor.score(query, s.text)) for s in sentences
], token_budget=600, relevance_threshold=0.4)
```
