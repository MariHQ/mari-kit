# GitHub polling and webhook stream

This project uses the same connector state for both paths:

1. scheduled polling ingests the authoritative repository snapshot;
2. a signed webhook becomes a bounded dirty hint;
3. the hint triggers an incremental canonical poll, updating/deleting documents
   and their vectors;
4. another repository change deliberately has no webhook delivery;
5. the next scheduled poll repairs the missed notification and republishes the
   retrieval index.

Deterministic verification:

```bash
set -a
. examples/github_pipeline/.env.example
set +a
python -m examples.github_pipeline.main
```

Live mode requires `MARI_EXAMPLE_MODE=live`, real connector/model variables,
and the exact received `GITHUB_WEBHOOK_JSON`, `GITHUB_WEBHOOK_SIGNATURE`, and
`GITHUB_WEBHOOK_EVENT`. The example never reads a default repository or token.
