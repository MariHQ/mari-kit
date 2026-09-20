> Agent handoff report. See [integrated results](README.md) for final validation and publication handling.

# Wave 5 — read-only publication review

Reviewer: OpenCode `deepseek/deepseek-flash` (wave-5 review owner).
Scope: accumulated uncommitted company-brain work, all waves, assessed for a
single publication commit/push. Working tree was live (other agents editing
concurrently). Read-only: no source edits, no staging, no git mutations, no
network, no installs. Only this file was written.

## Verdict

One concrete, reproducible release blocker. Everything else inspected is either
intentional or a documented limitation. The coordinator's stated plan (source
commit → regenerate inventory → docs commit) removes the blocker.

## Blocker 1 — inventory pins the parent revision, so the docs CI job fails after commit

- `mari-kit-landing/tools/generate_algorithm_inventory.py` derives the embedded
  revision from history: `git log -1 --format=%H -- src/mari_kit`.
- `docs/algorithm-inventory.json` currently records
  `"source_revision": "df931c43d1a2e88c82a667b34b1e33c5e3104a2d"` (= current
  `HEAD`), and `docs/algorithm-inventory.md` builds every source link from that
  same hash. Both were generated against the *uncommitted* working tree.
- The tree modifies `src/mari_kit` (e.g. `retrieval/indexes.py`,
  `knowledge/*.py`, `trajectories/workflows.py`). Once these are committed as
  `X`, `git log -1 -- src/mari_kit` returns `X`, not `df931c4`.
- CI `.github/workflows/ci.yml` docs job runs
  `generate_algorithm_inventory.py --check`, which regenerates content that now
  embeds `X` and compares it byte-for-byte to the checked-in file that embeds
  `df931c4` → `Stale inventory: docs/algorithm-inventory.json,
  docs/algorithm-inventory.md`, failing the build.
- Verified locally that `--check` currently exits 0, i.e. the failure is not
  caught before the commit. It is introduced *by* the commit.
- Concrete misleading-doc side effect: the index lists new symbols
  (`RevisionIndexDelta`, `RevisionBM25Index.with_deltas`) but links them into
  `df931c4`, where those definitions do not exist
  (`git show df931c4:src/mari_kit/retrieval/indexes.py` has `with_deltas` only
  on `BM25Index` and `ArtifactBM25Index`). Cited line numbers for every modified
  module therefore point at the wrong code until regeneration.

Remedy (matches the coordinator's plan): commit the `src/mari_kit` changes first
(as the only src-touching commit), then run
`.venv/bin/python mari-kit-landing/tools/generate_algorithm_inventory.py`
(no `--check`), then commit regenerated `docs/algorithm-inventory.{json,md}` in
a docs/artifacts commit that **does not touch `src/mari_kit`**. At CI, `HEAD`
then still resolves `git log -1 -- src/mari_kit` to the source commit, so
`--check` passes. Do not squash the two into one commit, and do not let the
second commit touch any file under `src/mari_kit`. No generator change is
required.

## Non-blocking findings and limitations

- Artifact hygiene: the committable untracked set is 75 curated `.md`/`.json`
  files under `artifacts/`; all `*.jsonl`, `*.log`, and `*.sqlite*` are matched
  by `.gitignore` for waves 1–4. The wave-5 ignore entries
  (`artifacts/company-brains-wave5/*.jsonl|*.log|*.sqlite*`) appeared in the
  working tree during this review (in-flight coordinator edit); confirm they are
  present in the final staged `.gitignore` before `git add`, since wave-5 raw
  `cache.jsonl`, `concurrency.jsonl`, and `review.jsonl` exist. `examples/
  **/__pycache__/` is also ignored. No raw OpenCode transcripts, no databases,
  and no provider secret values were found in the committable set (consistent
  with the coordinator's separate 157-file check).
- API compatibility: all `src/mari_kit` changes are additive and keyword-only
  with defaults, so existing callers are unaffected — new `RevisionIndexDelta`
  export, new `RevisionBM25Index.with_deltas`, `HNSWIndex.search` gains
  `exact_filter_threshold=0`/`search_starts=1`, and `document_evidence_ref`
  gains `scope=None`. Two intentional behavior changes are worth calling out in
  release notes: parsers now raise `ValueError` on conflicting duplicate
  `document_id`s instead of last-write-wins (`knowledge/_documents.py`), and
  `_position_key` changes internal BM25 tie-break ordering for corpora with ten
  or more units.
- CI/tooling: the two added steps (`python -m examples.company_brains`,
  `python -m examples.company_brains.durable`) ran here with the repo venv:
  exit 0, no network/credentials, under one second each. `ruff format --check
  src tests examples` and `ruff check src tests examples` both pass;
  `pytest --collect-only` reports 1079 tests, matching the stated baseline.
  Pyright runs only on `src`, so the new `examples/` code is exempt from
  type-checking by design.
- Docs: the new `mari-kit-landing/docs/agents/email.md` toctree entry is present
  in `agents/index.md`, there is no landing `_toc.yml` to update, and its
  `{include} ../../../docs/email.md` target exists. The docs job installs only
  `.[docs]`; the inventory generator is AST-only, so no examples import is
  needed there.
- Metrics prose: per-wave `artifacts/**/README.md` reports are historical and
  self-labelled as such; wave-1 still cites "751 tests" and "530 baseline"
  while the tree now collects 1079. Acceptable for point-in-time agent reports,
  but the root `README.md` should not repeat those counts (its diff adds links
  only, no numbers).
- In-flight risk: another agent is changing the durable cache schema (schema 3)
  during this review. Re-run `pytest` and the two CI example commands after that
  lands and immediately before push; the examples and
  `tests/test_brain3_cache.py`/`test_brain4_*` are the likely blast radius.

## Bounded checks run

```
.venv/bin/python mari-kit-landing/tools/generate_algorithm_inventory.py --check   # exit 0 (pre-commit only)
.venv/bin/ruff format --check src tests examples                                   # 333 files already formatted
.venv/bin/ruff check src tests examples                                            # All checks passed
.venv/bin/python -m pytest -q --collect-only                                       # 1079 tests collected
.venv/bin/python -m examples.company_brains                                       # exit 0, ~0.6s
.venv/bin/python -m examples.company_brains.durable                               # exit 0, ~0.9s
git show df931c4:src/mari_kit/retrieval/indexes.py | rg with_deltas               # new symbols absent at df931c4
```
