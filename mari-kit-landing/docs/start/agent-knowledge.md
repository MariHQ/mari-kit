[]{#agent-knowledge}[Supported composition]{.current-label}

# Build knowledge from completed agent work

## Flow

Mari consumes observable activity after the host runtime has executed it. A
caller-supplied model labels the workflow and phases. Mari checks those labels
against the event sequence, then validates any proposed memory mutation.

```{literalinclude} ../../../examples/quickstarts/agent_knowledge.py
:language: python
:caption: Completed activity to a reviewable knowledge proposal
```

The returned mutation plan contains proposed writes. The host can send those
proposals through evidence checks, human review, policy evaluation, and its own
storage transaction. The host retains runtime and commit authority.

| Input | Mari operation | Output |
|---|---|---|
| Completed tool events | `parse_trajectory_analysis` | Validated workflow, intent, phases, and rework |
| Existing knowledge and candidates | `plan_memory_mutations` | Add, update, delete, and no-op proposals |
| Approved plan | Host transaction | Application-owned stored knowledge |
