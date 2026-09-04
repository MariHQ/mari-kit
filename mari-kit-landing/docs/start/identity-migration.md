[]{#identity-migration}[Core]{.current-label}

# Identity migration

## Canonical document IDs

Document IDs now percent-encode `source_id` and `external_id` independently.
This preserves the structural pair when either component contains `/` or `%`.

| Structural identity | Canonical ID |
|---|---|
| `("a/b", "c")` | `a%2Fb/c` |
| `("a", "b/c")` | `a/b%2Fc` |

```{code-block} python
:caption: Convert stored structural fields to canonical IDs

from mari_components import canonical_document_id, parse_document_id

document_id = canonical_document_id(row.source_id, row.external_id)
source_id, external_id = parse_document_id(document_id)
```

Adapters should rebuild document-keyed projections from stored structural
fields. Sync manifests, lexical indexes, vector indexes, caches, and dependency
maps are derived projections. Rebuilding them keeps one identity encoding
throughout the application.

## Configured sources

`configured_source_id` hashes the non-secret settings that determine which
objects a connector observes. GitHub and GitLab expose `github_source_id` and
`gitlab_source_id` for their concrete configurations.

```{code-block} python
:caption: Bind sync state to one configured source

from mari_components.connectors import GitHubConfig, github_source_id

config = GitHubConfig(
    token=token,
    repository="acme/handbook",
    branch="main",
    paths=("docs/**",),
)
source_id = github_source_id(config)
```

A branch or path-scope change yields another source ID. The application starts
a fresh sync state for that configured view.
