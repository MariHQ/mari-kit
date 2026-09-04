[]{#memory-scopes}[Supported]{.current-label}

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
writable patterns. `propose_promotion` checks source readability and target
writability, then returns a decision record. On approval, the host creates a
new artifact linked to its origin. That new identity preserves the review boundary.

```{code-block} python
:caption: Propose a reviewable cross-scope promotion

from mari_components.governance import ScopeGrant, ScopePolicy, propose_promotion

policy = ScopePolicy(
    grants=(
        ScopeGrant(
            principal="agent:researcher",
            read=("agent:researcher", "project:mari"),
            write=("agent:researcher",),
        ),
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
assert proposal.allowed is False
assert proposal.reason == "target_not_writable"
```

Apply scope filtering in every host read path before retrieval scores are
computed. Direct ID reads and graph traversal must consult the same policy.
`ScopePolicy` supplies decisions through `allows`, and storage adapters enforce
them. Patterns use case-sensitive shell-style matching.

These policy scope strings express application access rules. `ScopeRef` carries
tenant and space identity in shared object references. Define an explicit
mapping between the two. Include policy changes in derived retrieval
dependencies as described in [dependency-aware updates](../start/dependency-updates.md).
Continue checking current access at read time, even for reusable outputs.

## Measures

| Case | Expected result |
|---|---|
| Unauthorized semantic match | Excluded from the ranked candidate set |
| Direct lookup of hidden ID | Denied identically to search |
| Agent-private promotion request | Proposal returned. No visibility change |
| Revoked origin | Host uses lineage to schedule derivative review or deletion |

::: source-block
**Papers and implementations**

[Governed Shared Memory for Multi-Agent LLM Systems](https://arxiv.org/abs/2606.24535){.paper}[Mem0](https://arxiv.org/abs/2504.19413){.paper}[Aegis Memory scope policy](https://github.com/quantifylabs/aegis-memory){.paper}[NIST access-control models](https://csrc.nist.gov/publications/detail/sp/800-162/final){.paper}

[Mari defines scope decisions and promotion records. Hosts remain responsible for authentication and storage isolation.]{.small}
:::
