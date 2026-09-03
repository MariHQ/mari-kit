[]{#contradiction-retrieval}[Current]{.current-label}

# SparseCL contradiction retrieval

## At a glance

| Configuration | ContraDoc reference Recall@10 | Interpretation |
|---|---:|---|
| Cosine only | `0.457` | Baseline using deterministic feature-hash embeddings |
| Cosine + Hoyer sparsity | `0.445` | The SparseCL term hurt by `0.012` without a SparseCL-trained encoder |

Do not enable the sparsity contribution merely because the equation is implemented. SparseCL relies on a separately trained sparse contrastive encoder; the deterministic ablation shows that the reranker alone does not create that signal.

:::{collapse} Worked sparse reranking example

| Candidate | Cosine | Hoyer contribution | Combined outcome |
|---|---:|---:|---|
| Same-topic contradiction | High | Sparse difference | Promoted |
| Same-topic agreement | High | Dense difference | Demoted |
| Unauthorized contradiction | High | Sparse difference | Removed before scoring |
:::

:::::::{container} diagram flow
::: card
**Query + corpus**[authorized passages only]{.small}
:::

*cosine*

::: card
**Top-K candidates**[same-topic prefilter]{.small}
:::

*Hoyer*

::: card
**Sparse rerank**[cos + α · sparsity]{.small}
:::

*→*

::: card
**ContradictionHit\[\]**[components + stable rank]{.small}
:::
:::::::

```{code-block} python
:caption: sparsecl.py

from mari_components.retrieval import (
    SparseContradictionCandidate, rank_sparse_contradictions,
)

hits = rank_sparse_contradictions(
    similarity_encoder(query), sparsecl_encoder(query),
    (SparseContradictionCandidate(
        passage_id=p.id,
        similarity_embedding=similarity_encoder(p.text),
        sparse_embedding=sparsecl_encoder(p.text),
    ) for p in corpus),
    alpha=0.4, candidate_limit=1000, limit=10,
    allowed_passage_ids=authorized_ids,
)
for hit in hits:
    audit(hit.cosine_similarity, hit.difference_sparsity, hit.score)
```

## Training objective

`sparse_contrastive_losses` evaluates the paper's Hoyer contrastive loss: contradictions are positives, similar non-contradictory passages are hard negatives, and the rest of the batch supplies soft negatives. It returns transparent NumPy loss terms for inspecting a training batch; the application trains `E_s` in PyTorch, JAX, or another framework.

::: source-block
**Paper**

[SparseCL: Sparse Contrastive Learning for Contradiction Retrieval](https://arxiv.org/abs/2406.10746){.paper}

[Mari implements Equations 1--3, cosine prefiltering, sparse reranking, authorization ordering, validation, and score traces. The Hoyer calculation was compared with the MIT-licensed Overcomplete implementation. The official SparseCL repository has no declared license, so no source from it is incorporated. Mari does not ship the trained encoder.]{.small}
:::


Contradiction retrieval asks which corpus passage explicitly disagrees with a query passage. Ordinary similarity alone tends to retrieve paraphrases. SparseCL combines topical cosine similarity with the sparsity of the difference between separately trained embeddings.

## How it works

1.  **Encode twice.** A standard encoder `E` produces similarity vectors; a SparseCL-trained encoder `E_s` produces vectors where contradictions differ in a small semantic subspace.
2.  **Authorize first.** Remove every passage outside `allowed_passage_ids` before computing scores.
3.  **Generate candidates.** Rank allowed passages by `cos(E(q), E(p))` and retain a large configurable candidate set---1,000 in the paper's example.
4.  **Measure sparse difference.** Compute normalized Hoyer sparsity over `E_s(q) − E_s(p)`. One-coordinate differences approach 1; dense differences approach 0.
5.  **Rerank.** Sort by `cosine + alpha × Hoyer`, with stable passage-ID ties, and retain every component in the result trace.
