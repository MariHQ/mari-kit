[]{#agent-knowledge}[Supported composition]{.current-label}

# Build knowledge from completed agent work

## Flow

From an installed repository checkout:

```{code-block} console
python -m examples.quickstarts.agent_knowledge
```

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

## Search observed knowledge

Use [conversation knowledge](../agents/conversation-knowledge.md) when the goal
is retrieving lessons and decisions from messages or visible tool observations.
Use [trajectory mining](../agents/trajectory-mining.md) for process structure
and [procedural learning](../agents/procedural-learning.md) for reviewable
procedure candidates. These paths retain distinct evidence and promotion gates.
