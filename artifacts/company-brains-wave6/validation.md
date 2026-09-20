> Agent handoff report. See [integrated results](README.md) for coordinator fixes and final verification.

# Wave 6 — cache-record validation probes

Owner: OpenCode `deepseek/deepseek-flash` (wave-6 validation owner).
Scope: `tests/test_brain6_validation.py` (new), plus
`examples/company_brains/durable/store.py` (one concrete decode bug fix). No
engine edits; `cache_records.py` unchanged (no bug reproduced). Read-only with
respect to other agents' wave-6 files (`admission.*`, `workload.*`,
`interleaved.*`, `test_brain6_decode_limits.py`, `engine.py`). Coordinator
commits.

## Verdict

Two concrete, reproducible source bugs in `SQLiteBrainStore.load_cache`, both
in the request path of `CompanyBrain.answer`. Both are fixed. No bug was
reproduced in `cache_records.py`, so the validator was left untouched. One
semantic limitation is confirmed and asserted on purpose: the unkeyed checksum
is corruption detection, not authentication, so a writer that can re-seal a
record can still inject unsupported prose.

## Bug 1 — non-UTF-8 `BLOB` payload escapes `load_cache` as `UnicodeDecodeError`

`load_cache` caught only `json.JSONDecodeError`, but `json.loads` accepts
`bytes` and decodes them first. A BLOB payload that is not valid JSON text
raises `UnicodeDecodeError` (a sibling of `JSONDecodeError`, not a subclass).

Reproduction (host corrupts its own `cache.payload`):

```text
payload = b"\xff\xff\xff"   -> UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff
payload = b"\xff\xfe\x00"   -> UnicodeDecodeError: 'utf-16-le' codec can't decode ...
```

`load_cache` raised, and the exception propagated out of `CompanyBrain.answer`,
violating the invariant that a malformed record is an ordinary cache miss.

## Bug 2 — over-long integer literal escapes `load_cache` as bare `ValueError`

Python's default `sys.get_int_max_str_digits()` is 4300. `json.loads` of a
payload containing a longer integer literal raises a plain `ValueError` (not
`JSONDecodeError`). An extreme evidence offset is exactly such a literal.

Reproduction:

```text
payload = '{"start":' + "9"*5000 + '}'
  -> ValueError: Exceeds the limit (4300 digits) for integer string conversion
```

Again the exception escaped `load_cache` and `answer`. A 4299-digit literal
still round-trips; 4301+ raises.

## Hardening also covered — pathologically nested JSON

`json.loads` of `"[" * 100_000 + "]" * 100_000` raises `RecursionError`, which
also escaped the original handler and crashed the request.

## Fix (`examples/company_brains/durable/store.py`)

```python
try:
    payload = json.loads(row[0])
except (ValueError, TypeError, RecursionError):
    # A corrupt or hostile payload — invalid JSON text, non-UTF-8 bytes,
    # an over-long integer literal, or pathologically nested JSON — is a
    # cache miss, never an exception out of the request path.
    return None
return payload if isinstance(payload, dict) else None
```

`json.JSONDecodeError` and `UnicodeDecodeError` are both `ValueError`
subclasses, so the tuple covers both reproduced failures plus the nesting case.
Valid UTF-8/UTF-16 JSON bytes still decode to a dict (positive control).

Note: the parallel wave-6 agent's `tests/test_brain6_decode_limits.py` asserts
the same integer-limit behavior and now passes against this fix; before the fix
it fails, so the two changes are consistent.

## Coverage added (`tests/test_brain6_validation.py`, 51 cases)

Store decoding:

- non-object JSON (`null`, `[]`, `42`, `true`, `"text"`, `3.14`, `nan`, `{}`)
  and undecodable text (empty, truncated, BOM, trailing comma) are safe misses;
- non-UTF-8 BLOBs are safe misses and a subsequent request still answers
  (Bug 1 regression);
- over-long integer literals inside a full record are safe misses (Bug 2);
- deeply nested payloads are safe misses (hardening);
- `NaN` payloads decode but fail the codec and are misses;
- interleaved corrupt payloads recover and the following request is a genuine
  hit again;
- valid UTF-8/UTF-16 JSON bytes still decode (positive control).

Validator (`cache_record_matches_request`) via a re-sealing writer:

- a property-like matrix over nine fields × JSON-compatible poison values
  (wrong types, empty values, wrong shapes, unknown document ids) — every case
  recovers as a grounded cache miss;
- re-sealed cross-request binding (question, user, scope, schema) is a miss;
- a re-sealed wrong digest is a miss; accidental (un-re-sealed) corruption of
  the answer, digest, disposition, or question is a miss via the checksum;
- dependency `content_digest` mismatch and quote not in the live body are
  misses; a re-sealed unchanged record is still reused (positive control).

Extreme and invalid evidence offsets:

- invalid spans (single-sided, `None`-paired, negative, zero-length, reversed,
  float, bool, string types, huge negative) are misses;
- a stop far past the body is clamped by Python slicing and still matches; a
  4001-digit offset round-trips and is handled without exception (`10**4000`);
  omitting both `start` and `end` (no span) is valid; a huge `start` is a safe
  miss.

Trust boundary (asserted, not "protected"):

- an `insufficient_evidence` record that still carries matching valid evidence
  and dependencies is a valid reusable hit;
- a re-sealed record with a valid digest, dependencies, revision, exact quote
  and span but unsupported answer prose (`"The refund window is 900 days."`) is
  **served**. This records that the unkeyed checksum provides no protection
  against a malicious re-sealer.

An additional bounded randomized probe (600 seeded re-sealed mutations over the
same fields, including `start`/`end` and unknown extra fields) produced zero
unexpected exceptions and zero unsafe results.

## Validation

```text
.venv/bin/python -m pytest tests/test_brain6_validation.py   -> 51 passed
.venv/bin/python -m pytest                                   -> 1192 passed
.venv/bin/ruff check  store.py test_brain6_validation.py     -> All checks passed
.venv/bin/ruff format --check ...                            -> already formatted
```

The 1192 total includes other wave-6 agents' concurrently added tests
(`admission`, `decode_limits`, `pressure`, `workload`) and grows as those agents
add cases; the pre-wave baseline was 1102. No engine file was edited by this
owner. (One full-suite run during concurrent editing observed the other agent's
`test_brain6_pressure.py` red; it passes in isolation and in the final full run,
and is unrelated to the `load_cache` decode path.)

## Reproduce

```bash
.venv/bin/python -m pytest tests/test_brain6_validation.py -q
.venv/bin/python -m pytest tests/test_brain6_decode_limits.py -q
```

To see the original failures, revert `load_cache` to `except json.JSONDecodeError`
and run the two regression tests; seven cases fail with `UnicodeDecodeError`,
`ValueError`, or `RecursionError` out of `load_cache`/`answer`.
