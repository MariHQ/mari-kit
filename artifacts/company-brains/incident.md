# Incident-response builder integration

The DeepSeek Flash builder produced `examples/company_brains/incident.py` and
`tests/test_company_brain_incident.py`. Its OpenCode session stopped after an
external temporary-directory permission rejection. The coordinating agent
completed verification and this report within the workspace.

The scenario binds answers to runbook sections and Slack evidence, applies a
runbook edit and thread revision, removes the communications source, and uses
`impacted_artifacts` to report selective invalidation. Detection and escalation
guidance remain reusable; mitigation, the whole-runbook digest dependency, and
the removed-source answer require refresh.

All 13 incident tests pass, including invalid citations, missing sections,
deleted sources, and conservative whole-document fallback. The module is also
executed by the combined company-brain runner.

No library defect blocked this scenario. The digest is a dependency fixture,
not a generated digest. Review, authorization, model calls, durable storage,
and execution of incident procedures remain host responsibilities.
