[]{#parsers}[Supported]{.current-label}

# Knowledge parsers

## Behavior

| Mari provides | Caller provides |
|---|---|
| Typed schemas, evidence resolution, ordering recovery, and safe fallbacks | Model prompt, inference, and task-specific quality |
| An uncertain result when a required row or citation is invalid | The threshold for retry, review, or rejection |

The parsers validate injected extraction results. Corpus evidence helps select
the model. Parser guarantees cover structure, attribution, and failure behavior.


:::{collapse} Example malformed-batch recovery

| Requested claim | Model row | Parsed result |
|---|---|---|
| Claim A | Valid supported row with evidence | Supported assessment |
| Claim B | Missing row | Uncertain assessment |
| Claim C | Malformed evidence | Uncertain assessment with parse issue |
| Claim D | Valid row returned out of order | Restored to Claim D position |
:::



Models return JSON-like values. Parsers resolve evidence against supplied
document and section revisions and return immutable typed values. Research
establishes each task formulation. Mari implements the deterministic validation
boundary around the cited model.

## How it works

Each parser requires the recipe's top-level collection, validates every required
field and enum, resolves evidence through the contract below, derives audit
signals, and constructs frozen result types. Claim meaning stays with the
caller. Batch claim assessment keys rows to caller order. Absent rows become
`uncertain`, and malformed rows leave valid siblings available.

:::{container} diagram stages
model proposal*→*schema*→*exact evidence*→*revision binding*→*typed candidate
:::

| Parser | Produces | Research-backed task | Academic sources |
|----|----|----|----|
| `parse_facts` | `FactCandidate` | Atomic claims and optional document-level relations with evidence | [FActScore](https://arxiv.org/abs/2305.14251){.paper} · [DocRED](https://arxiv.org/abs/1906.06127){.paper} |
| `parse_claim_assessments` | `FactAssessment` | Supported, contradicted, or uncertain verdicts. Decisive rows require evidence | [FEVER](https://arxiv.org/abs/1803.05355){.paper} |
| `parse_decisions` | `DecisionCandidate` | Decision-related utterance extraction with evidence-based interpretation | [Hsueh & Moore](https://aclanthology.org/N07-1004/){.paper} · [Karan et al.](https://aclanthology.org/2021.sigdial-1.56/){.paper} |
| `parse_answer` | `GroundedAnswer` | Evidence-selected document QA, citations, or explicit insufficient evidence | [QASPER](https://arxiv.org/abs/2105.03011){.paper} · [ALCE](https://arxiv.org/abs/2305.14627){.paper} |
| `parse_answer_candidates` | `AnswerCandidate[]` | Reusable question-answer pairs bound to supporting passages | [QASPER](https://arxiv.org/abs/2105.03011){.paper} |
| `parse_glossary` | `GlossaryCandidate[]` | Term-definition relations, aliases, and source spans | [DeftEval](https://arxiv.org/abs/2008.13694){.paper} |
| `parse_digest` | `DigestSummary` | Document-wide and topic summaries with separately inspectable evidence | [QAGS](https://arxiv.org/abs/2004.04228){.paper} · [SummaC](https://arxiv.org/abs/2111.09525){.paper} |
| `parse_impact` | `ImpactAssessment` | In-scope affected-document proposals followed by deterministic dependency checks | Mari contract. No claimed benchmark reproduction |
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

**`grounding_coverage` measures lexical coverage.** It is a Mari-specific audit
signal motivated by citation completeness. Exact quote validation catches
fabricated citations. Logical entailment remains a separate evaluation.

## Source parser functions and options

| Function | Main options | Failure behavior |
|---|---|---|
| `parse_markdown` | `tables`, `recover_unclosed_fences`, `parser_id` | Returns an unclosed-fence warning or error and retains the recovered block |
| `parse_html` | `parser_id`, `recover` | Reports unmatched and implicitly closed tags. `recover=False` promotes recovery warnings to errors |
| `parse_delimited` | `identity_fields`, delimiter or sniffing, quote character, header, `strict_width` | Rejects a malformed-width row in strict mode. Valid siblings survive |
| `parse_json_lines` | `identity_fields`, `parser_id` | Each malformed or non-object line is positioned independently |
| `parse_json_array` | `identity_fields`, `parser_id` | Retains parsed object siblings and positions non-object or malformed members |
| `parse_python` | Repository, revision, path and parser ID | Syntax errors produce an empty, positioned result. Symbol extraction requires valid syntax |

`ParseIssue` contains `code` and `message`. Severity and an optional subject
add context. The record also carries an exact character span.
`ParseResult.succeeded` becomes true when every issue stays below error
severity. Warnings and accepted values remain available in the result.

```{code-block} python
:caption: Keep accepted records beside malformed siblings

from mari_components.documents import parse_json_lines

result = parse_json_lines(
    payload,
    source_id="warehouse:policies",
    revision=object_etag,
    identity_fields=("policy_id", "jurisdiction"),
)

store(result.values)
observe(result.issues)
```

| Structured-ingest fixture | Before | Current |
|---|---:|---:|
| Fields with exact raw spans | `0/12` | `12/12` |
| Syntactically accepted records with record spans | `0/5` | `5/5` |
| Schema-drift violations | `1` | `3` |
| Invalid integer/date values rejected | `0/2` | `2/2` |

::: source-block
**Format and parser references**

[CommonMark block syntax](https://spec.commonmark.org/){.paper}[WHATWG HTML parsing](https://html.spec.whatwg.org/multipage/parsing.html){.paper}[RFC 4180 CSV](https://www.rfc-editor.org/rfc/rfc4180){.paper}[JSON Lines](https://jsonlines.org/){.paper}[Python AST](https://docs.python.org/3/library/ast.html){.paper}[Tree-sitter](https://tree-sitter.github.io/tree-sitter/){.paper}

[Markdown-It-Py and html5lib are MIT-licensed differential references. Tree-sitter and its Python grammar are MIT licensed.]{.small}
:::
