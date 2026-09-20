# Company brains: sixth wave

Three parallel OpenCode `deepseek/deepseek-flash` agents investigated oversized
cache admissions, interleaved multi-user workloads, and malformed cache records.
The coordinator added independent reproductions, integrated further fixes, and
verified the resulting changes. [Sessions](sessions.json).

## Fixes

- An oversized authorized view is removed before it can force generic LRU
  eviction of useful smaller views. Obsolete versions of the same user's view
  are still removed, including when the replacement is oversized.
- Independent integration testing found that base-size admission could evict
  a warm view before index growth revealed the new view was oversized. Search
  misses and default extractive generation now build the required index before
  admission. Callback-only answers retain lazy indexing. Existing views that
  grow oversized are removed before other views.
- Invalid cache JSON, invalid byte encodings, overlong integer literals, and
  recursion-limit failures become recoverable misses instead of request errors.
  Checksum verification also catches recursion failures from deeply nested
  records that the JSON decoder accepted. Schema v3 is unchanged.

## Admission reproduction

With a 32 KiB estimated budget, a small user warms one 5,674-byte view, followed
by a user authorized to read a much larger source. Before the fix, that larger
request evicted the small view and itself, leaving the cache empty. Afterward,
the small view remains and its next request performs **zero snapshot reloads**
(previously one). Authorized search results are unchanged.

[Before](admission-before.json), [after](admission-after.json).
The independent tight-budget regression also covers the case where the new
base view fits individually but would evict the old view before index growth.

## Interleaved workloads

240 documents, 16 users, four queries each, four cached views, no byte limit.
Each ordering uses the same multiset of 64 user/query requests on a fresh brain.
Hits and misses come from actual snapshot-read counters. [Results](interleaved.json).

| Request ordering | View-cache hits | Snapshot misses | Hit rate |
| --- | ---: | ---: | ---: |
| Consecutive queries per user | 48 | 16 | 75% |
| Round robin across users | 0 | 64 | 0% |
| One user's queries separated by blocks of other-user traffic | 45 | 19 | 70.3% |

All count bounds held. This qualifies the earlier consecutive-user hit-rate
measurement: it does not predict reuse under arbitrary interleaving. The third
ordering designates a user whose requests are spread out; it does not increase
that user's total request count. Latency samples are retained in the report,
but no machine-time threshold determines success.

## Validation and reproduction

**1,193 tests pass**, up from 1,102. Lint, formatting, Pyright, wheel/sdist build,
installed-wheel durable lifecycle, original examples, all eight company-brain
scenarios, strict documentation build, inventory freshness, and browser sidebar
checks pass. This wave does not change model prompts or claim new live-model
quality results.

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m benchmarks.company_brain_admission_probe
.venv/bin/python -m benchmarks.company_brain_interleaved --documents 240 \
  --users 16 --queries-per-user 4 --count 4 --no-byte-budget \
  --output /tmp/brain-interleaved.json
.venv/bin/python -m examples.company_brains.durable
```

Memory budgets cover estimated retained views, not temporary index construction
or total process RSS. The cache remains LRU; the round-robin result is an
observed limitation, not a claimed fix. Host identity, database writers, and
access-counter maintenance remain trusted. The checksum is not authentication
or semantic validation. Agent handoff reports reflect their own snapshots;
the integrated results above include the coordinator's additional fixes.
