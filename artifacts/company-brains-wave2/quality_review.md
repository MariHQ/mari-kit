> Integration note: this is an agent report from the development run. See [the integrated results](README.md) for final fixes, measurements, and verification.

# Wave 2 quality review

Owner: quality reviewer. Scope: `quality_corpus.py`, `quality_eval.py`, and the
quality-related wiring (cross-checked `live_eval.py` and `engine.py`). No source
files were edited. Only owned files were written:
`artifacts/company-brains-wave2/quality_review.md` and
`tests/test_brain2_quality_review.py`. No git changes, no full-suite run, no
model calls, no raw JSONL transcripts read.

Artifacts may still change while other agents work. Findings below are pinned to
the revision reviewed at 2026-09-19 ~17:30 local:

| File | MD5 |
| --- | --- |
| `examples/company_brains/durable/quality_corpus.py` | `deb17e774b4bc99989360fb841f68745` |
| `examples/company_brains/durable/quality_eval.py` | `ab8b345a15043b900add5a732a865b34` |
| `examples/company_brains/durable/live_eval.py` | `4513549b43fa03258c531a72a695ea08` |

## Method

1. Read the shared contract and the wave-1 reports to separate host
   responsibilities from corpus/evaluator defects.
2. Re-derived every label property independently from the public case schema
   (`quality_corpus.cases()`, `build_prompt`, `authorized_documents`) and the
   public evaluator (`quality_eval.evaluate_case`, `run`, `summarize`).
3. Cross-checked the builder tests (`tests/test_brain2_quality.py`) and the
   breaker tests (`tests/test_brain2_quality_adversarial.py`) so this report
   credits existing coverage instead of duplicating it.
4. Ran only focused checks (below), never the whole suite.

## Verified correct (no action needed)

- **Scale and coverage.** 25 cases, unique ids, all seven required categories
  (`current_policy`, `superseded_policy`, `conflict`, `ambiguity`,
  `missing_info`, `restricted_evidence`, `irrelevant_matches`) and 13 source
  domains.
- **Label/evidence consistency.** Grounded cases always have allowed evidence;
  abstention cases never do. `allowed_evidence_ids` is always a subset of the
  case documents.
- **Gold terms are supported.** Every `required_terms` entry is recoverable from
  the allowed-evidence bodies, every `forbidden_terms` entry is absent from the
  allowed evidence, and required/forbidden sets are disjoint. `conflict.*`,
  `superseded.*` and `irrelevant.*` place their forbidden term in a disallowed
  (or non-allowed) document, so those traps are real rather than vacuous.
- **Prompt leakage is closed.** `build_prompt` returns exactly
  `{question, documents}` from `authorized_documents`, never the `GRADING_FIELDS`
  (`quality_corpus.py:140`). The earlier document-`id`-only filter that leaked
  the superseded revision is fixed by storing/using the authorised revision
  tuple by `(document_id, revision)` identity (`quality_corpus.py:99-137`); the
  breaker already pinned this and the builder landed the fix. `live_eval.py`
  now uses `visible_documents()`/`authorized_documents` rather than the whole
  corpus, so no withheld revision reaches a live prompt either.
- **Metric separation is real and intentional.** `evaluate_case` reports
  `citation_valid`, `answer_correct`, `abstained`, `stale`, `disposition_correct`
  and raw citation counters separately (`quality_eval.py:115-198`), and
  `citation_valid` is deliberately authorization+currency, not gold-evidence
  matching (the breaker asserts a "perfectly cited wrong answer" is citation
  valid but answer incorrect). `summarize` carries explicit denominators and
  `invalid_outputs` counts failures in every denominator (`quality_eval.py:226`).
- **Invalid output never disappears.** `run` records callback exceptions and
  `{}` as invalid outputs that still count in all denominators
  (`quality_eval.py:296-305`).
- **Fixture mode is deterministic and JSON-serialisable.** `run()` twice returns
  equal, `json.dumps`-able output.

## Findings

### F1 — `conflict.nda_review` gold term is quoted verbatim in the question (corpus, minor)

`quality_corpus.py:600-605`: question `"Must a mutual NDA be reviewed by legal
before signature?"`, `required_terms=("reviewed by legal",)`. The lexical
correctness proxy can be satisfied by echoing the prompt, so this case does not
require the model to extract a proposition from evidence.

Exact fix: use a discriminative term that only appears in the evidence, e.g.
`required_terms=("before signature",)` (or `"every mutual nda"`), keeping
`forbidden_terms=("need no review",)`. This is the only fully-quoted gold case;
`superseded.travel_class` is fine because its second required term
(`"six hours"`) is unique to the evidence.

### F2 — `allowed_evidence_ids` cannot express revision identity for superseded cases (corpus label, moderate)

For the four `superseded_policy` cases the allowed current revision and the
withheld superseded revision share one `document_id` (`quality_corpus.py:120-125`
stores only `document_id` strings). `allowed_evidence_ids` therefore also matches
the retired revision: e.g. `superseded.refund_window` yields
`allowed_evidence_ids == ["handbook/refunds"]` while `documents` contains both
`refund-v2` and `refund-v3`. `quality_eval` never reads
`allowed_evidence_ids`, so nothing fails today, but the label is ambiguous and
any external consumer that trusts it can credit the wrong revision.

Exact fix: add a revision-aware companion field (mirroring
`authorized_documents`), e.g. `allowed_evidence`: the tuple of
`KnowledgeDocument`s, exported as `[{"document_id", "revision"}]`, or store
`allowed_evidence_ids` as `"<document_id>@<revision>"`. Preserve the existing
`allowed_evidence_ids` field for contract compatibility.

### F3 — `conflict.client_meals` has no stated resolution rule (corpus label, moderate)

`quality_corpus.py:280-284` and `580-595`: the expected grounded answer is the
finance `$75` cap with `$150` forbidden. The sales doc says `"$150 per person
during deal cycles"`, i.e. a *scoped* claim, and neither document states
authority or supersession. A defensible answer may cite both scopes, and a
model following the live instruction ("if current sources conflict without a
resolution ... abstain") may abstain. The resolution rests only on
source/title/`updated_at`, which is an implicit host policy, not evidence.

Exact fix (pick one): (a) add an explicit precedence sentence to the finance
doc, e.g. "Finance expense policy governs all sales playbooks."; (b) move the
case to `ambiguity` with `expected_disposition="insufficient_evidence"`; or
(c) record the authority rule in `ANSWER_INSTRUCTION`/host policy and keep the
case. `conflict.change_freeze` is clean (only the engineering doc states the
start date). `conflict.nda_review` is defensible but depends on the same
implicit legal-over-sales precedence; fix as in F1 and consider (a)/(c) there
too.

### F4 — implicit authority precedence vs the live abstention instruction (host/corpus, moderate)

The `conflict.*` labels assume "authoritative owner policy beats another team's
doc", while `live_eval.ANSWER_INSTRUCTION` tells the model to abstain on
unresolved conflict. A live model can therefore be graded wrong for obeying the
host instruction. This is a host-contract mismatch, not an evaluator bug.

Exact fix: either encode precedence in document text/metadata (F3) or state the
precedence rule in the host answer instruction, e.g. append "A policy owned by
the accountable team (finance, legal, engineering) takes precedence over another
team's FAQ/playbook for the same question." Then live grading and fixture
labels agree.

### F5 — `stale` can never be non-zero from the fixture baseline (metric coverage, minor)

The superseded revisions are withheld from every prompt, so fixture
`default_generate` has no way to produce a stale citation; the fixture report
shows `stale={"stale":0,"total":20}`. The metric is correct (independently
proven by `tests/test_brain2_quality_review.py::test_stale_citation_metric_is_exercisable`,
where a crafted old-revision prediction yields `stale=True`,
`citation_valid=False`), but the corpus alone never exercises it.

Exact fix: add one live-callback regression case or keep the builder's
`test_live_stale_prediction_increases_stale_rate`, and state in the report that
fixture mode cannot exhibit stale answers by construction.

### F6 — current-policy forbidden terms are vacuous hallucination guards (corpus, minor)

`current.refund_window`, `current.mfa`, `current.pto` and `current.sev1_sla`
forbid terms that appear nowhere in the corpus (`30/60/90 days`, `sms codes are
accepted`, `20/30 days`, `1 hour/4 hours`). They guard against hallucination but
add no discrimination. Acceptable, but note that these four cases are the
"easy" current-policy fixtures: single/clean evidence with no real distractor.
If harder current-policy cases are wanted, use one real competing value as in
the conflict cases.

### F7 — `superseded_policy` tests authorization, not model supersession (corpus, minor)

Because the retired revision is withheld, the model never has to reason that an
archived policy is stale; the case only proves the host exposes the current
revision. This matches the corpus docstring, but the category name overstates
what is measured. If supersession *reasoning* is in scope, add a case where both
revisions are authorized and the current document explicitly says it supersedes
the old one; grading can then require the current value and forbid the retired
one while keeping `citation_valid` separate.

## Host responsibilities (not defects)

- Semantic correctness is not, and is not claimed to be, provable by these
  lexical proxies (`quality_eval.py:20`; `live_eval.py:148`). Citation validity is
  authorization+currency, intentionally independent of answer correctness.
- Live model calls, credentials, and end-to-end integration are coordinator
  responsibilities; this review made none.
- `examples/company_brains/durable/engine.py` is out of the corpus/evaluator
  ownership and was only read to confirm that authorized-document handling
  (`access_snapshot`, `authorized_fingerprint`) is separate from the quality
  fixtures.

## Independent tests

`tests/test_brain2_quality_review.py` (owned, 19 tests) checks properties not
already asserted by the builder/breaker suites: required terms answerable from
allowed evidence; forbidden terms absent from allowed evidence; required and
forbidden disjoint; distractor forbidden terms present in disallowed documents;
evaluator-label and metadata non-leakage; domain variety; invalid/supported
separation across all cases; uncited grounded answers not credited; and
exercisability of the stale/unauthorized/fabricated citation metrics.

## Commands and results

```text
.venv/bin/ruff check tests/test_brain2_quality_review.py          # All checks passed!
.venv/bin/ruff format --check tests/test_brain2_quality_review.py # 1 file already formatted
.venv/bin/python -m pytest tests/test_brain2_quality_review.py -q
    # 18 passed, 1 failed
    # FAILED test_grounded_required_terms_are_not_entirely_quoted_in_the_question
    #        -> ['conflict.nda_review']   (expected red; see F1)
.venv/bin/python -c 'from examples.company_brains.durable import quality_eval as q; q.run()'
    # fixture: invalid_outputs 0/25
    # citation_validity 11/11, answer_correctness_proxy 9/11
    # disposition_accuracy 16/25, abstention expected 14/25, stale 0/20
```

No full-suite run was performed, per the shared contract. The one red test is
intentional and documents F1; it goes green as soon as the corpus makes that
gold term discriminative.

## Limitations

- Findings are pinned to the hashes above; the corpus and evaluator changed twice
  during the review (the earlier document-`id` prompt leak was already fixed by
  the builder before this review, having been caught by the breaker test).
- Lexical term matching proves presence/absence of strings, not entailment; no
  claim is made about real-model or semantic quality.
- `allowed_evidence_ids` is unused by `quality_eval`; this review therefore
  cannot and does not claim the evaluator grades against the gold evidence set.
- No live API calls were made, so live-mode behavior (F4) is reasoned about from
  the instruction text, not measured.
