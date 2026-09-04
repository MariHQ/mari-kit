[]{#adaptive-retrieval}[Reference]{.current-label}

# Adaptive retrieval and compression

## Behavior

| Mechanism | Mari decides | Evidence boundary |
|---|---|---|
| CRAG | Use, supplement, or replace retrieved context from score thresholds | SciFact gold relevance exercised all three routes. The relevance evaluator remains yours |
| FLARE | Retrieval trigger for low-confidence future tokens | QASPER answer novelty exercises masking. Real calibration comes from your model |
| Self-RAG | Candidate utility and whether retrieval is requested | Gold relevance validates score composition. Reflection-token prediction needs a separate measure |
| Chain-of-Note | Retrieved, parametric, or unknown answer source | Gold qrels validate deterministic source choice. Note judgment quality needs a separate measure |
| RECOMP | Which complete sentences fit a token budget | QASPER retained `16.6%` of tokens with evidence recall `0.330` in the measured configuration |

:::{collapse} Example routing examples

| Signal pattern | Decision | Next operation |
|---|---|---|
| High relevance | Accept | Use retrieved corpus evidence |
| Ambiguous relevance | Supplement | Add an external retrieval arm |
| Low relevance | Replace | Discard current candidates and retrieve again |
| Low-confidence future tokens | Retrieve | Mask uncertain tokens and search with the remainder |
:::



Retrieval can be triggered, revised, rescored, or compressed at explicit
decision points across a model call.

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
