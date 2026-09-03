[]{#parsers}[Current]{.current-label}

# Knowledge parsers

## At a glance

| Mari provides | Caller provides |
|---|---|
| Typed schemas, evidence resolution, ordering recovery, and safe fallbacks | Model prompt, inference, and task-specific quality |
| An uncertain result when a required row or citation is invalid | The threshold for retry, review, or rejection |

These are validation parsers, not bundled extraction models. Corpus evidence helps select the injected model; parser guarantees concern structure, attribution, and failure behavior.


:::{collapse} Worked malformed-batch recovery

| Requested claim | Model row | Parsed result |
|---|---|---|
| Claim A | Valid supported row with evidence | Supported assessment |
| Claim B | Missing row | Uncertain assessment |
| Claim C | Malformed evidence | Uncertain assessment with parse issue |
| Claim D | Valid row returned out of order | Restored to Claim D position |
:::



Models return JSON-like values. Parsers resolve all evidence against supplied document and section revisions and return immutable typed values. Research establishes each task formulation; Mari implements a deterministic validation boundary rather than the cited model.

## How it works

Each parser first requires the recipe's top-level collection, then validates every required field and enum, resolves evidence through the exact contract below, derives deterministic audit signals, and constructs frozen result types. It never repairs a claim's meaning. Batch claim assessment is the exception to fail-fast parsing: rows are keyed back to caller order, absent rows become `uncertain`, and individually malformed rows do not erase valid siblings.

:::{container} diagram stages
model proposal*→*schema*→*exact evidence*→*revision binding*→*typed candidate
:::

| Parser | Produces | Research-backed task | Academic sources |
|----|----|----|----|
| `parse_facts` | `FactCandidate` | Atomic claims and optional document-level relations with evidence | [FActScore](https://arxiv.org/abs/2305.14251){.paper} · [DocRED](https://arxiv.org/abs/1906.06127){.paper} |
| `parse_claim_assessments` | `FactAssessment` | Supported, contradicted, or uncertain verdicts; decisive rows require evidence | [FEVER](https://arxiv.org/abs/1803.05355){.paper} |
| `parse_decisions` | `DecisionCandidate` | Decision-related utterance extraction without treating topical language as proof | [Hsueh & Moore](https://aclanthology.org/N07-1004/){.paper} · [Karan et al.](https://aclanthology.org/2021.sigdial-1.56/){.paper} |
| `parse_answer` | `GroundedAnswer` | Evidence-selected document QA, citations, or explicit insufficient evidence | [QASPER](https://arxiv.org/abs/2105.03011){.paper} · [ALCE](https://arxiv.org/abs/2305.14627){.paper} |
| `parse_answer_candidates` | `AnswerCandidate[]` | Reusable question-answer pairs bound to supporting passages | [QASPER](https://arxiv.org/abs/2105.03011){.paper} |
| `parse_glossary` | `GlossaryCandidate[]` | Term-definition relations, aliases, and source spans | [DeftEval](https://arxiv.org/abs/2008.13694){.paper} |
| `parse_digest` | `DigestSummary` | Overall and topic summaries with separately inspectable evidence | [QAGS](https://arxiv.org/abs/2004.04228){.paper} · [SummaC](https://arxiv.org/abs/2111.09525){.paper} |
| `parse_impact` | `ImpactAssessment` | In-scope affected-document proposals followed by deterministic dependency checks | Mari contract; no claimed benchmark reproduction |
| `parse_refinement` | `RefinementEdit[]` | Bounded, attribution-aware, fact-preserving edit proposals | [RARR](https://arxiv.org/abs/2210.08726){.paper} · [FactEditor](https://arxiv.org/abs/2007.00916){.paper} |

```{code-block} python
:caption: answer.py

from mari_components.knowledge import parse_answer

raw = model(question, documents)
answer = parse_answer(question, documents, raw)
print(answer.disposition)         # grounded | insufficient_evidence
print(answer.grounding_coverage)  # deterministic text coverage
print(answer.evidence[0].quote)  # exact source text
```

Additional deterministic helpers include `normalize_claim`, `deduplicate_fact_candidates`, `grounding_coverage`, and `excerpt`. Recoverable batch drift is handled conservatively: assessment rows are restored to caller order, missing rows become uncertain, and good rows survive alongside invalid ones. Structured fact qualifiers preserve subject, relation, object, scope, validity, and conditions.

**`grounding_coverage` is not entailment or confidence.** It is a Mari-specific lexical audit signal motivated by citation completeness. Exact quote validation prevents fabricated citations but does not prove that every paraphrase follows logically from its evidence.
