# Slack polling and event stream

This project deliberately runs both ingestion paths against the same sync
manifest and canonical thread identity:

1. scheduled polling ingests the initial thread and advances a timestamp cursor;
2. a signed Events API reply acts as a dirty hint and immediately refetches the
   complete thread without changing the poll cursor;
3. another reply's event is deliberately lost;
4. the next poll discovers that reply row, refetches its root thread, and repairs
   the canonical document.

Deterministic verification:

```bash
set -a
. examples/slack_event_pipeline/.env.example
set +a
python -m examples.slack_event_pipeline.main
```

Live mode additionally requires the exact received `SLACK_EVENT_JSON` and
`SLACK_SIGNATURE`. `SLACK_HISTORY_TOKEN` is optional and explicit; when absent,
the bot token is used for history calls. Nothing is synthesized in live mode.
