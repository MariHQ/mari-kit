# Reliable Slack answer

```bash
set -a; . examples/slackbot_reliable_answers/.env.example; set +a
python -m examples.slackbot_reliable_answers.main
```

The fake mode uses the same orchestration as live mode. Live mode uses the
official OpenAI SDK for OpenAI embeddings and DeepSeek's OpenAI-compatible
endpoint. It performs one customer-answer round, records the completed events,
then performs one separate trajectory-analysis round. The Slack SDK posts a
thread reply only when `MARI_SLACK_POST=true`; live mode is otherwise read-only.

Here, a reviewed workflow means Mari Cloud's human-approved trajectory intent
and read-only fast path. The match starts a real asynchronous document retrieval
task before the host agent chooses a tool. It is not a general workflow engine.
Complete response reuse requires the higher cache threshold and current source
revisions. A highly relevant newer document falls back to the LLM unless a user
has marked it non-impacting.

Live mode can load the styleguide and product documents directly from GitHub.
Required variables and the explicit Slack-post switch are in `.env.example`.
