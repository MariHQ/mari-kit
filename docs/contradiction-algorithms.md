# Contradiction algorithms

Mari implements two distinct contradiction tasks. They are not interchangeable.

## Corpus contradiction retrieval: SparseCL

[SparseCL](https://arxiv.org/abs/2406.10746) retrieves a passage that
contradicts a query passage. It uses two encoder paths:

- a standard sentence encoder `E`, whose cosine similarity keeps candidates on
  the same topic;
- a SparseCL-trained encoder `E_s`, where a contradiction is trained to produce
  a sparse difference vector.

For embeddings of dimension `d`, Mari implements the paper's normalized Hoyer
difference sparsity:

```text
Hoyer(h1, h2) = (sqrt(d) - ||h1-h2||1 / ||h1-h2||2) / (sqrt(d) - 1)
```

and its retrieval score:

```text
F(q, p) = cosine(E(q), E(p)) + alpha * Hoyer(E_s(q), E_s(p))
```

```python
from mari_components.retrieval import (
    SparseContradictionCandidate,
    rank_sparse_contradictions,
)

hits = rank_sparse_contradictions(
    similarity_encoder(query),
    sparsecl_encoder(query),
    (
        SparseContradictionCandidate(
            passage_id=passage.id,
            similarity_embedding=similarity_encoder(passage.text),
            sparse_embedding=sparsecl_encoder(passage.text),
        )
        for passage in corpus
    ),
    alpha=0.4,              # tune on a held-out validation set
    candidate_limit=1000,   # cosine prefilter before sparse reranking
    limit=10,
    allowed_passage_ids=authorized_ids,
)
```

Authorization is applied before cosine candidate generation. Every hit retains
cosine, Hoyer, combined score, and stable rank. `candidate_limit=None` performs
an exact scan of the allowed corpus. Identical sparse embeddings receive zero
difference sparsity instead of evaluating the undefined `0/0` ratio.

`sparse_contrastive_losses` is a NumPy conformance implementation of the
paper's training objective. Contradictions are positives, semantically similar
passages are hard negatives, and other batch pairs are soft negatives. It is
not an autodiff training framework; PyTorch, JAX, or another trainer can compare
its per-example loss against Mari's result.

## Within-document self-contradiction: RRC-DSCD

[Think Wider, Detect Sharper](https://aclanthology.org/2025.emnlp-main.67/)
addresses document-level self-contradiction detection (DSCD): whether one
multi-sentence document contradicts itself and which sentences conflict. Its
two-stage model training uses teacher-distilled chain-of-thought SFT followed by
GRPO with accuracy, reference-coverage, and format rewards.

Mari does not ship the teacher or train an LLM. It implements the reusable,
testable boundary around that process:

```python
from mari_components.verification import (
    document_contradiction_rewards,
    validate_document_contradiction,
)

assessment = validate_document_contradiction(
    sentence_count=len(sentences),
    judgment=model_output.judgment,
    evidence_sentence_ids=model_output.evidence_sentence_ids,
    reasoning=model_output.reasoning,  # accepts [i], [i-j], and [i]-[j]
)

rewards = document_contradiction_rewards(
    assessment,
    expected_judgment=example.is_self_contradictory,
    gold_evidence_sentence_ids=example.conflicting_sentence_ids,
    format_valid=model_output.matches_required_format,
)
```

The validator expands sentence ranges, rejects references outside the document,
requires localized evidence for a positive judgment, and rejects contradiction
evidence attached to a negative judgment. Reference coverage is the number of
distinct reasoning-referenced sentences divided by the document sentence
count.

The reward executor follows the paper's positive-example rule: an incorrect
judgment scores `0`; a correct judgment with no evidence hit scores `-1`; a
correct judgment with evidence scores `1 + matched / gold`. Negative examples
use binary judgment accuracy. Format, coverage, and accuracy remain separate
components for an external GRPO trainer.

See [contradiction reference validation](contradiction-reference-validation.md)
for the MIT/Apache-2.0 comparison. In particular, the published Equation 5 and
the authors' current MIT `rewards.py` differ in evidence normalization and the
zero-hit penalty; Mari follows the paper and records the discrepancy explicitly.

## Boundary between the tasks

SparseCL finds potential conflicts *between a query and a large passage corpus*.
DSCD evaluates and localizes conflicts *inside one document*. A knowledge system
can use SparseCL to propose cross-source contradiction candidates and DSCD to
audit the internal consistency of each newly ingested or synthesized artifact.
Neither vector sparsity nor reference coverage proves that a contradiction is
factually correct; evidence review or an NLI/verifier stage remains necessary.
