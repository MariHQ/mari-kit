[]{#memory-scopes}[Current]{.current-label}

# Knowledge scopes and promotion

## Behavior

| Scope | Typical writer | Typical readers | Promotion condition |
|---|---|---|---|
| `session:*` | Current runtime | Current session | Consolidation accepts durable value |
| `agent:*` | One agent role | Same role | Reviewed or policy-approved sharing |
| `user:*` | User interaction | Authorized user applications | Explicit purpose and consent |
| `project:*` | Team sources and agents | Project principals | Evidence and project policy |
| `organization:*` | Governed publishers | Organization principals | Privileged approval |

## How it works

Callers define scope paths. Each principal receives explicit readable and
writable patterns. Promotion creates a new artifact linked to its origin. The
new identity preserves the review boundary.

```{code-block} python
:caption: Propose a reviewable cross-scope promotion

from mari_components.governance import ScopeGrant, ScopePolicy, propose_promotion

policy = ScopePolicy(
    grants=(
        ScopeGrant(principal="agent:researcher", read=("project:mari",), write=("agent:researcher",)),
    )
)

proposal = propose_promotion(
    artifact_id="finding:2406.10746",
    source_scope="agent:researcher",
    target_scope="project:mari",
    principal="agent:researcher",
    policy=policy,
)
# The proposal still requires a privileged commit or application review.
```

Every read path applies scope filtering before retrieval scores are computed. Direct ID reads and graph traversal use the same policy, preventing a common isolation gap.

## Measures

| Case | Expected result |
|---|---|
| Unauthorized semantic match | Excluded from the ranked candidate set |
| Direct lookup of hidden ID | Denied identically to search |
| Agent-private promotion request | Proposal returned. No visibility change |
| Revoked origin | Promoted derivative marked for review or deletion |

::: source-block
**Papers and implementations**

[Governed Shared Memory for Multi-Agent LLM Systems](https://arxiv.org/abs/2606.24535){.paper}[Mem0](https://arxiv.org/abs/2504.19413){.paper}[Aegis Memory scope policy](https://github.com/quantifylabs/aegis-memory){.paper}[NIST access-control models](https://csrc.nist.gov/publications/detail/sp/800-162/final){.paper}

[Mari defines scope decisions and promotion records. Hosts remain responsible for authentication and storage isolation.]{.small}
:::
