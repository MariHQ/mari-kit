# Knowledge parser foundations

Mari parsers are validation boundaries for model-produced structured data.
They do not implement the cited models or claim equivalent benchmark results.
The papers establish the task formulations; Mari adopts the reusable contracts
and applies stricter deterministic checks against the exact source revisions
provided by the application.

## Shared evidence contract

All evidence-bearing parsers use the same resolution path:

```text
model row
   │
   ├─ document ID exists in the supplied set
   ├─ quote is an exact source substring
   ├─ repeated quote is disambiguated by section ID
   ├─ character span is recomputed from source text
   └─ document and section revisions are copied from current source state
          ↓
       Evidence
```

This contract operationalizes two distinctions emphasized by citation and
document-QA research:

- Citation correctness: cited material supports the nearby output.
- Citation completeness: the output's claims are covered by citations.

[ALCE](https://arxiv.org/abs/2305.14627) evaluates correctness and completeness
separately, while [QASPER](https://arxiv.org/abs/2105.03011) records supporting
evidence alongside answers. Mari handles the mechanical half: citations must
resolve exactly and remain revision-addressable. Semantic support remains a
separate assessment or review step.

## Parser-to-research map

| Mari parser | Research task | Contract adopted by Mari | Important difference |
|---|---|---|---|
| `parse_facts` | Atomic factual decomposition and document-level relation extraction | Atomic claims, optional subject/relation/object structure, exact evidence | [FActScore](https://arxiv.org/abs/2305.14251) evaluates atomic support; [DocRED](https://arxiv.org/abs/1906.06127) studies cross-sentence relations. Mari validates proposed rows but does not run either model. |
| `parse_claim_assessments` | Evidence-based fact verification | `supported`, `contradicted`, or `uncertain`; evidence required for decisive verdicts | The labels follow [FEVER](https://arxiv.org/abs/1803.05355). Invalid or missing evidence becomes `uncertain` instead of preserving an unsupported verdict. |
| `parse_answer` | Evidence-selected document QA and attributed generation | Grounded answer or explicit insufficient-evidence disposition | [QASPER](https://arxiv.org/abs/2105.03011) couples answers with evidence; [ALCE](https://arxiv.org/abs/2305.14627) measures citation quality. Mari additionally binds citations to revisions and rejects a grounded answer with no evidence. |
| `parse_answer_candidates` | Question-answer pair construction from source material | Question, answer, and exact evidence remain one immutable candidate | The parser validates candidate QA pairs; it does not generate questions or estimate answerability. |
| `parse_decisions` | Decision-related utterance detection and summarization | A decision statement must carry exact evidence | Decision detection is established in [Hsueh and Moore (2007)](https://aclanthology.org/N07-1004/) and its topic-bias risks are examined by [Karan et al. (2021)](https://aclanthology.org/2021.sigdial-1.56/). Mari does not infer decisions from topical vocabulary itself. |
| `parse_glossary` | Definition extraction | Term-definition pairs, aliases, deduplication, and exact evidence | [DeftEval](https://arxiv.org/abs/2008.13694) separates definition sentence classification, sequence labeling, and relation extraction. Mari accepts a generated pair only after source resolution. |
| `parse_digest` | Abstractive summarization with factual consistency | Overall and per-topic summaries each retain evidence | [QAGS](https://arxiv.org/abs/2004.04228) and [SummaC](https://arxiv.org/abs/2111.09525) show that fluency and source consistency are separate. Mari enforces citation presence and identity but does not claim that exact quotation alone proves every paraphrase. |
| `parse_impact` | Evidence-linked change analysis | Affected IDs must belong to the supplied document set; optional evidence is source-resolved | This is a Mari product-knowledge contract rather than a reproduction of a standard NLP benchmark. Dependency-based invalidation is deterministic after parsing. |
| `parse_refinement` | Evidence-preserving text revision | Bounded replacements must identify an exact original substring and include a reason | [RARR](https://arxiv.org/abs/2210.08726) studies attribution-aware revision and [FactEditor](https://arxiv.org/abs/2007.00916) studies fact-based editing. Mari emits proposals only; it never edits the source document. |

## Atomic facts

Long passages commonly mix supported and unsupported propositions. FActScore's
central move is to decompose generated text into atomic facts before measuring
support. Mari preserves that granularity and can retain structured relation
fields for later graph projection.

```python
from mari_components.knowledge import parse_facts

facts = parse_facts(documents, {
    "facts": [{
        "claim": "Enterprise refunds close after 30 days.",
        "atomic_claims": ["Enterprise refunds have a time limit.",
                          "The time limit is 30 days."],
        "subject": {"canonical": "enterprise refund"},
        "relation": "has_time_limit",
        "object": "30 days",
        "evidence": [{
            "document_id": documents[0].document_id,
            "quote": "Enterprise refunds close after 30 days.",
        }],
    }],
})
```

`atomic_claims` and relation fields remain qualifiers. Mari does not silently
split a claim or invent a canonical ontology.

## Claim verification and abstention

FEVER's three-way formulation separates lack of evidence from contradiction.
Mari uses `uncertain` for the former and degrades malformed decisive rows to
that state.

```python
assessments = parse_claim_assessments(
    claims,
    documents,
    {"assessments": [{
        "claim": claims[0],
        "verdict": "supported",
        "explanation": "The policy states the same limit.",
        "evidence": [{"document_id": policy.document_id,
                      "quote": "Refunds close after 30 days."}],
    }]},
)

assert assessments[0].verdict in {"supported", "contradicted", "uncertain"}
```

Rows are restored to caller claim order. A missing row becomes `uncertain`;
one bad citation does not discard other valid assessments in the batch.

## Answers and citation quality

```python
answer = parse_answer(question, documents, {
    "answer": "Enterprise refunds close after 30 days.",
    "disposition": "grounded",
    "evidence": [{"document_id": policy.document_id,
                  "quote": "Enterprise refunds close after 30 days."}],
})

assert answer.evidence[0].revision == policy.revision
assert answer.evidence[0].section_revision
```

When the sources do not answer the question, the model can return
`insufficient_evidence`. This is not converted into a synthetic answer.

## Definitions, decisions, summaries, and revisions

```python
terms = parse_glossary(documents, glossary_output)
decisions = parse_decisions(documents, decision_output)
digest = parse_digest(documents, digest_output)
impact = parse_impact(documents, impact_output)
edits = parse_refinement(document, refinement_output, maximum_edits=4)
```

These parsers share structural validation but retain task-specific invariants:
definition aliases must be arrays, decision statements require evidence,
digests require at least one evidence-linked topic, affected document IDs must
be in scope, and proposed replacements must point to exact original text.

## What the scores mean

`grounding_coverage` is a Mari-specific lexical audit signal. It combines token
overlap with small, saturating credits for multiple citations and independent
documents. It is motivated by the separation of citation completeness and
correctness in ALCE, but it is not ALCE's metric, entailment, calibrated
confidence, or a truth probability.

Use semantic claim assessment, contradiction checks, authority policy,
freshness, and human review separately. Exact evidence resolution prevents
fabricated citations; it does not prove that a paraphrase is logically entailed.
