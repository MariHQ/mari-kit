> Integration note: this is an agent report from the development run. See [the integrated results](README.md) for final fixes, measurements, and verification.

# Wave 2 quality breaker report

Owned deliverables:

- `tests/test_brain2_quality_adversarial.py` — 28 adversarial tests over
  `quality_eval.evaluate_case` / `run` and the `quality_corpus` contract.
- `artifacts/company-brains-wave2/quality_breaker.md` — this report.

No source modules were edited. No git/network/credential/subagent actions.

## Commands and results

```
.venv/bin/ruff check tests/test_brain2_quality_adversarial.py      # All checks passed
.venv/bin/ruff format tests/test_brain2_quality_adversarial.py     # unchanged
.venv/bin/python -m pytest tests/test_brain2_quality_adversarial.py -q
    # 28 passed
```

Inspected revisions at report time:

| file | sha256 (first 16) | lines |
| --- | --- | --- |
| `examples/company_brains/durable/quality_eval.py` | `a8fdc1bd638b9a9c` | 313 |
| `examples/company_brains/durable/quality_corpus.py` | `7667cfd9befcf15a` | 726 |
| `tests/test_brain2_quality_adversarial.py` | `efacac847abf13fa` | 642 |

Fixture `run()` result for reference: 25 cases, 0 invalid outputs,
citation validity 11/11, answer-correctness proxy 9/11, disposition accuracy
16/25, abstention accuracy 16/25, stale 0/20.

## Adversarial coverage (requested scenarios)

| scenario | test |
| --- | --- |
| perfectly cited wrong answer | `TestMetricSeparation::test_perfectly_cited_wrong_answer_valid_citation_but_incorrect` (citation `True`, correctness `False`) |
| correct answer, invalid quote | `...::test_correct_answer_with_nonexistent_quote_is_not_credited` (same text; citation flips `True`→`False`; invalid output fails) |
| fabricated source | `...::test_fabricated_source_is_an_invalid_citation` (citation `False`, `fabricated_citations>=1`) |
| required abstention, empty evidence | `...::test_required_abstention_with_empty_evidence_is_scored_as_abstained`, `...::test_required_abstention_without_explicit_disposition_is_abstained` |
| stale superseded policy | `...::test_stale_superseded_answer_is_flagged_separately` (stale `True`/correctness `False`; fresh twin stale `False`/correctness `True`) |
| denied source | `...::test_denied_source_citation_is_invalid_even_when_quote_matches` (citation `False`, `unauthorized_citations>=1`) |

Metric separation, denominator preservation and answer-key leakage:

- `TestMetricSeparation` asserts four independent dimensions resolve as separate
  observable keys: citation validity, answer-correctness proxy, abstention, stale.
- `TestInvalidOutputPreserved` asserts an empty prediction keeps every metric
  dimension, `run()` keeps invalid cases in `invalid_outputs`,
  `citation_validity.total` and `answer_correctness_proxy.total`, and that a
  raising callback is recorded as `generate_error` rather than dropped.
- `TestAnswerKeyLeakage` asserts `run(generate=...)` calls the generator for all
  25 cases with only the question and the case's `authorized_documents`; no
  evaluator label key (`GRADING_FIELDS`) appears in args/kwargs and no withheld
  revision reaches the callback.
- `TestCorpusContract` pins the case schema, unique IDs, per-`(document_id,
  revision)` identity, allowed-evidence subset, authorized-document subset,
  restricted withholding, `build_prompt` key set, and that
  `superseded.refund_window`'s prompt excludes the retired body while a correct
  current answer still scores grounded/citation-valid/correct.

## Defects vs host responsibilities

### 1. Superseded revision leaked into prompts — FIXED during this session

My first inspection found `authorized_documents()` filtering by
`document_id` only, so a retired revision that shares `document_id` with the
current one (e.g. `handbook/refunds` `refund-v2` vs `refund-v3`) was still
returned by `build_prompt`. `evaluate_case` then passed two conflicting
documents with the same ID to `parse_answer`, whose `document_lookup` raises
`conflicting documents share document_id`, so every correct current answer on a
superseded case scored invalid.

The quality builder replaced ID filtering with object identity and an explicit
`authorized_documents` tuple (line 120). Verified fixed: the withheld body is
absent from the prompt and the correct current answer scores
`prediction_valid/citation_valid/answer_correct = True`, `stale = False`.

Host responsibility: none remaining. This is now pinned by
`test_superseded_case_prompt_excludes_the_withheld_revision` and
`test_correct_current_answer_on_a_superseded_case_scores_as_grounded`.

### 2. String-form evidence is parse-valid but citation-invalid (low severity)

Probe on `current.refund_window` with `evidence: [<full body string>]`:

```
prediction_valid=True grounded=True citation_valid=False
current_citations=0 evidence_count=0 error=""
```

`parse_answer` resolves a bare string quote to the single authorized document
(valid), but `evaluate_case._raw_evidence` keeps only `Mapping` rows, so the
citation counters see zero rows and `citation_valid` is `False` with
`evidence_count=0`. The host engine always emitting object records
(`engine.py:115 _evidence_record`) keeps this off the production path, but the
evaluator is internally inconsistent for an input its own validator accepts.

Exact fix (host/quality builder): in `_raw_evidence`, normalize string rows the
same way `parse_answer` does (a nonempty string quote resolves to the unique
authorized document when exactly one body contains it), or compute
current/stale/unauthorized/fabricated counts from the validated
`GroundedAnswer.evidence` (which is already revision-bound) plus a separate raw
scan for fabricated IDs. Either makes `citation_valid` agree with
`prediction_valid` for string citations.

### 3. Aggregate report does not expose fabricated/unauthorized citation counts

`summarize()` reports `citation_validity`, `answer_correctness_proxy`,
`disposition_accuracy`, `abstention`, `stale`, but only `stale` gets a citation
sub-count. `fabricated_citations` and `unauthorized_citations` exist per case
only. Because `parse_answer` repairs a fabricated ID when exactly one authorized
document contains the quote, a fabricated-source prediction can be
`prediction_valid=True` and even `answer_correct=True` (`citation_valid=False`,
`fabricated_citations=1`). The failure is observable per case but not in the
aggregate or per-category summary.

Exact fix (quality builder): add to `summarize()` and `_by_category()`

```python
"unauthorized_citations": sum(row["unauthorized_citations"] for row in results),
"fabricated_citations": sum(row["fabricated_citations"] for row in results),
```

with a `total`/`rate` shape mirroring `citation_validity`. Optionally let the host
decide whether fabrication should also force `prediction_valid=False`; I did not,
because the current behavior preserves the required separation between "the
answer text is right" and "the citation is valid".

### 4. Stale detection depends on evidence carrying `revision`

`evaluate_case` counts a same-`document_id` row as stale only when a string
`revision` differs from the authorized revision; a row that omits `revision` is
counted as current. Probe on `superseded.refund_window` citing the withheld
`refund-v2` body without `revision` yields `stale=False` (still invalid because
the quote is not in the authorized current body). The host engine emits
`revision` (`engine.py:118`), and `live_eval.ANSWER_INSTRUCTION` asks models only
for `document_id` and a quote, so the live stale rate is structurally near zero.

Host responsibility: if live stale-answer rate is a decision metric, either add
`revision` to the answer instruction, or have the evaluator mark a quote that
matches only a withheld same-`document_id` revision as stale using
`case["documents"]`. The corpus already catches the stale *answer text* through
`forbidden_terms` (`30 days`), so `answer_correctness_proxy` still drops.

### 5. Lexical proxy substring false positives (documented limitation)

`_terms_match` uses `term in folded`, so `required_terms=("45 days",)` is
satisfied by `"145 days"`. The module docstring and contract already state the
proxy cannot prove semantics; I did not encode this weak behavior in a test.
Exact fix if stricter: match with a token-boundary regex built from
`re.escape(term)` and `\b`.

## Limitations of this breaker work

- All tests are deterministic/offline; no live model was called (coordinator
  owns live checks). Verification is against the two fixture-derived modules and
  the engine's documented evidence shape, not against real model outputs.
- The tests pin metric *semantics and separation*, not gold answer quality. The
  lexical proxy cannot prove entailment, and finding 5 shows it can be fooled.
- The metric adapter resolves dimensions by concept tokens (`citation_valid`,
  `citation valid`, nested `citation.valid`, etc.), so a rename does not
  silently drop a dimension; a merged/removed dimension fails loudly.
- Corpus count is 25 (contract requires >=24); additions that keep the schema
  remain compatible with `test_corpus_has_at_least_twenty_four_cases`.
