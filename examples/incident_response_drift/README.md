# Incident-response knowledge drift

This example starts with a GitHub runbook containing independent detection,
mitigation, and escalation sections plus an incident Slack thread. It creates
grounded mitigation and escalation answers and treats them as reviewed cache
entries.

A new runbook revision changes only the mitigation section. Mari then proves:

- the mitigation answer and workflow are impacted;
- a whole-runbook digest is conservatively impacted;
- the escalation answer and workflow remain reusable because their exact
  section hash is unchanged; and
- the impact report identifies the changed section rather than merely saying
  that the containing document changed.

```bash
set -a; . examples/incident_response_drift/.env.example; set +a
python -m examples.incident_response_drift.main
```
