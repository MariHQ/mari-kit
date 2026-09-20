> Integration note: this is an agent report from the development run. See [the integrated results](README.md) for final fixes, measurements, and verification.

# Quality builder report (wave 2)

Owner: quality builder. Scope:
`examples/company_brains/durable/quality_corpus.py`,
`examples/company_brains/durable/quality_eval.py`, owned tests
`tests/test_brain2_quality.py`, owned report `quality_builder.md`.
Status: **complete — focused checks green.**

## What was built

- `quality_corpus.py`: a data-only, network-free corpus of **25 cases** across the
  seven contract categories (`current_policy` 4, `superseded_policy` 4,
  `conflict` 3, `ambiguity` 3, `missing_info` 3, `restricted_evidence` 4,
  `irrelevant_matches` 4) spanning refunds, security, HR, support, finance,
  engineering, legal, compliance, facilities, ops, product, IT, travel, and
  privacy domains. Each case carries the contract fields plus an explicit
  `authorized_documents` view.
- `build_prompt(case)` is the only case→prompt path. It returns exactly
  `{"question", "documents"}`; evaluator-only fields (`expected_disposition`,
  `required_terms`, `forbidden_terms`, `allowed_evidence_ids`) are unreachable.
- `quality_eval.py`: `evaluate_case(case, prediction)` and
  `run(generate=None)` with fixture (deterministic offline BM25 baseline) and
  live (`generate(question, documents)`) modes. It validates every prediction
  with `mari_kit.knowledge.parse_answer` and independently classifies raw
  citations (current / stale / unauthorized / fabricated).

## Metrics (explicit denominators)

| Metric | Numerator / denominator |
| --- | --- |
| citation validity | expected-grounded cases whose citations resolve to authorized, current evidence / all expected-grounded cases |
| answer correctness proxy | expected-grounded cases whose text passes required/forbidden term checks / all expected-grounded cases |
| disposition accuracy | cases whose validated disposition matches the label / all cases |
| abstention rate | validated abstentions / all cases |
| abstention accuracy | cases where abstained matches the label / all cases (invalid counts as wrong) |
| stale-answer rate | grounded attempts citing a superseded revision / all grounded attempts |

`invalid_outputs` is reported separately and **is counted as failure** in
citation, answer, disposition, and abstention denominators — invalid output
never disappears. `citation validity` is decoupled from the lexical proxy:
citing a distractor is still a valid citation but fails the term proxy, while a
stale revision label fails citation validity and raises the stale rate.

## Commands and results

```
.venv/bin/python -m pytest tests/test_brain2_quality.py -q
20 passed in 2.85s

.venv/bin/ruff check examples/company_brains/durable/quality_corpus.py \
  examples/company_brains/durable/quality_eval.py tests/test_brain2_quality.py
All checks passed!

.venv/bin/ruff format --check ...   # 3 files already formatted
```

Fixture-mode metrics over the 25 cases (deterministic BM25 baseline):

```
case_count 25
invalid_outputs            0 / 25  (0.00)
citation_validity         11 / 11  (1.00)
answer_correctness_proxy   9 / 11  (0.82)
disposition_accuracy      16 / 25  (0.64)
abstention                 5 / 25  (0.20), expected 14, accuracy 16 / 25
stale                      0 / 20 grounded attempts
```

The baseline's misses are concentrated in `ambiguity`, `irrelevant_matches`,
and `missing_info`, where positive BM25 lexical overlap causes over-grounding;
that is expected baseline behaviour and is exactly what the metrics expose.

## Defects vs host responsibilities

1. **`parse_answer` ignores the supplied evidence `revision`.** `_evidence`
   resolves the revision from the authorized document and discards
   `value["revision"]`, so a callback that labels an authorized document with a
   superseded revision is accepted. This is an observable freshness blind spot
   when parsing is used alone. Host/engine responsibility: revalidate freshness
   from the store (the durable engine already does this via
   `authorized_fingerprint` and cached dependency revisions), or add the
   revision check below upstream.
2. **Authorization cannot be filtered by `document_id` alone.** Superseded and
   current revisions of one provider object share a `document_id`. Filtering a
   corpus by ID leaks the retired body, and passing both revisions to
   `document_lookup`/`parse_answer` raises "conflicting documents share
   document_id". Host responsibility: authorize by object identity
   `(document_id, revision)`, as `quality_corpus.authorized_documents` does.
3. **`KnowledgeDocument` is not hashable.** Its frozen dataclass hash includes
   the unhashable `metadata` mapping, so documents cannot go into sets. Not a
   bug in the contract, but hosts must key by `(document_id, revision)` or
   object identity, which this code does.
4. **Stale detection needs raw labels, not just parser output.** Because of
   defect 1, the evaluator inspects the raw prediction to classify citations;
   grading only the parsed `GroundedAnswer` would report 100% stale-free even
   for stale labels.

## Exact recommended fixes

- Upstream (Mari Kit, for the coordinator to file): in
  `knowledge/facts.py::_evidence`, when an evidence row supplies a non-empty
  `revision`, reject it unless it equals `document.revision` (raise
  `MalformedModelOutput`). This makes freshness a validation invariant instead
  of a caller convention. Until then, hosts must keep the explicit revision
  check used here.
- Engine/host: continue keying cached-answer dependencies and authorization on
  `(document_id, revision)` and re-fingerprint the authorized set before serving;
  never filter visibility by `document_id` alone.
- No change needed to the quality contract; `run(generate=...)` accepts
  engine-style payloads (`answer`, `disposition`, `evidence`, `cache_hit`) and
  works with or without an evidence `revision` label.

## Limitations

- The correctness proxy is purely lexical (required/forbidden term substrings).
  It proves term presence, not semantic correctness, and intentionally cannot
  reward correct paraphrase; case authors must prefer stable explicit
  propositions.
- `stale-answer rate` is measured on static per-request views via revision
  labels. It approximates, but does not replace, an end-to-end test that edits,
  deletes, or revokes against a live store and then re-asks the engine.
- Fixture mode is a BM25/extractive baseline, so its scores describe that
  baseline, not any provider model. Live metrics require a coordinator-supplied
  callback; this module makes no network or model calls.
- The corpus is synthetic and small (25 cases); it is a smoke contract, not a
  representative benchmark.
