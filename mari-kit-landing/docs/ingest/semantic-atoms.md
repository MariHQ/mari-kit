[]{#semantic-atoms}[Supported]{.current-label}

# Semantic atoms and retrieval-time chunks

## Behavior

One deterministic edit was applied to the MIT-licensed Pi LLM Wiki README:
insert one paragraph near the start and change one existing phrase.

| Storage unit | Units before / after | Reused | Changed units to encode | Invalidated fixed units |
|---|---:|---:|---:|---:|
| Semantic atoms | 221 / 222 | 220 atoms in both representations | 2 raw + 2 contextual vectors | 1 old atom tombstoned. 2 parent sections invalidated |
| Fixed 500-token chunks | 7 / 7 | 0 | 7 | 7 |

The source is pinned at revision `55510fac8e17` and SHA-256
`1ab44172…b4ea97`. This measures invalidation under one controlled edit.
Retrieval quality and embedding latency require separate measurements. Atoms
are stored and indexed. Chunks are assembled for presentation.

:::::::::::::{container} diagram flow
:::{container} card
**Normalized Markdown**[one immutable source revision]{.small}
:::
**→**
:::{container} card
**Semantic atoms**[paragraph · list item · table row · code]{.small}
:::
**→**
:::{container} card
**Atom vectors**[raw + heading-contextual]{.small}
:::
**→**
:::{container} card
**ANN or MUVERA**[candidate atoms or sections]{.small}
:::
**→**
:::{container} card
**Runtime expansion**[neighbor atoms under token budget]{.small}
:::
:::::::::::::

## Extract semantic atoms

`semantic_atoms` consumes Mari's parsed-document IR. Headings supply context.
Paragraphs, list items,
table rows, and code blocks become independently versionable units.

```{code-block} python
:caption: Parse Markdown and create stable atom identities

from mari_components.documents import parse_markdown, semantic_atoms

parsed = parse_markdown(
    markdown,
    artifact_id="pricing",
    revision="sha256:source-revision",
)
atoms = semantic_atoms(
    parsed.values[0],
    maximum_atom_characters=2_000,
    fallback_average_characters=1_000,
)

atom = atoms[17]
print(atom.atom_id, atom.heading_path, atom.content_hash)
print(markdown[atom.start:atom.end])
```

| Field | Identity behavior |
|---|---|
| `source_id` | Stable caller-owned page identity |
| `source_revision` | Immutable source version. Excluded from `atom_id` |
| `section_id` / `heading_path` | Semantic location and contextual embedding prefix |
| `ordinal` | Current ordering field. Identity uses content and location |
| `content_hash` | SHA-256 of NFKC text with cosmetic whitespace collapsed |
| `atom_id` | Source + section + kind + content hash + local duplicate occurrence |
| `start`, `end` | Exact character span in the current source revision |

Repeated identical atoms in one section receive a local occurrence suffix so
IDs remain unique. Inserting unrelated content earlier in the page preserves
their identity.

::: source-block
**Evidence**

[Markdown syntax trees and source maps](https://github.com/executablebooks/markdown-it-py){.paper}[W3C Web Annotation selectors](https://www.w3.org/TR/annotation-model/#selectors){.paper}
:::

## Use content-defined spans for oversized blocks

Semantic boundaries take precedence. When a paragraph or code block exceeds
`maximum_atom_characters`, `content_defined_spans` applies a deterministic
Gear-hash-style boundary rule between minimum, average, and maximum sizes.

```{code-block} python
:caption: Bound a giant block with content-defined boundaries

from mari_components.documents import content_defined_spans

spans = content_defined_spans(
    giant_code_block,
    minimum_characters=512,
    average_characters=1_024,
    maximum_characters=2_048,
)
segments = [giant_code_block[start:end] for start, end in spans]
```

The small fallback draws from FastCDC. It uses Gear-style rolling state and
skips cuts before the minimum. Its character-span contract uses one mask. A
byte-compatible adapter can supply FastCDC's normalized dual-mask
distribution.

::: source-block
**Evidence**

[FastCDC paper and evaluation](https://www.usenix.org/conference/atc16/technical-sessions/presentation/xia){.paper}[Canonical permissive Rust implementation](https://docs.rs/fastcdc/latest/src/fastcdc/v2016/mod.rs.html){.paper}
:::

## Align source revisions with Myers or patience diff

Both algorithms operate on arbitrary hashable sequences. Atom alignment uses
the exact normalized content hashes.

```{code-block} python
:caption: Choose an alignment algorithm explicitly

from mari_components.documents import (
    AtomDiffAlgorithm, align_atoms, myers_diff, patience_diff,
)

myers_spans = myers_diff(old_hashes, new_hashes)
patience_spans = patience_diff(old_hashes, new_hashes)

alignment = align_atoms(
    old_atoms,
    new_atoms,
    algorithm=AtomDiffAlgorithm.PATIENCE,
    modification_threshold=0.55,
)
```

| Algorithm | Mechanics | Useful property |
|---|---|---|
| Myers | Expands edit-distance frontiers and backtracks a shortest insert/delete script | Minimal edit script. Worst-case `O((N+M)D)` time |
| Patience | Selects values unique on both sides, finds their longest increasing subsequence, recursively aligns gaps, and falls back to Myers | Stable anchors in reordered or repetitive documents |

:::{collapse} Exact alignment for the motivating sequence

| Old | New | Result |
|---|---|---|
| A | A | unchanged |
| n/a | X | inserted |
| B | B | unchanged |
| C | C′ | replacement region. Lexical matching pairs it as modified |
| D | D | unchanged |
| E | E | unchanged |
:::

Within replacement regions, `align_atoms` greedily pairs same-kind atoms under
the same heading when token-set Jaccard similarity clears the caller threshold.
The pairing records provenance. Changed text receives a new embedding.

::: source-block
**Evidence**

[Myers: An O(ND) Difference Algorithm and Its Variations](https://doi.org/10.1007/BF01840446){.paper}[Patience diff implementation history](https://git-scm.com/docs/diff-options#Documentation/diff-options.txt---diff-algorithmpatience){.paper}
:::

## Plan selective invalidation

```{code-block} python
:caption: Reuse exact atoms and defer parent vectors

from mari_components.documents import plan_atom_refresh

plan = plan_atom_refresh(
    alignment,
    rebuild_parent_embeddings_eagerly=False,
)

embedding_store.reuse_many("raw", plan.reuse_raw_embeddings)
embedding_store.reuse_many("contextual", plan.reuse_contextual_embeddings)
embedding_store.embed_many("raw", plan.embed_raw_atom_ids)
embedding_store.embed_many("contextual", plan.embed_contextual_atom_ids)
atom_store.tombstone_many(plan.tombstone_atom_ids)
# The host decides when to rebuild plan.invalidate_section_ids.
```

| Alignment result | Raw atom vector | Contextual atom vector | Section/page vector |
|---|---|---|---|
| Unchanged | Reuse | Reuse when heading path is unchanged | Keep unless another child changed |
| Unchanged text moved to another heading | Reuse | Rebuild with the new heading path | Invalidate old and new parents |
| Inserted | Create | Create | Invalidate parent |
| Modified | Create new, tombstone old | Create new, tombstone old | Invalidate parent |
| Deleted | Tombstone | Tombstone | Invalidate parent |

The refresh plan contains IDs and invalidations. It leaves embeddings and writes
to the host. Atom retrieval remains authoritative. The host can rebuild parent
embeddings lazily.

::: source-block
**Evidence**

[Content-defined chunking for shift-resistant deduplication](https://www.usenix.org/conference/atc16/technical-sessions/presentation/xia){.paper}[W3C PROV revision and derivation](https://www.w3.org/TR/prov-dm/){.paper}
:::

## Aggregate atom ANN hits by parent

Every atom can live in an ordinary vector index. `aggregate_atom_hits` groups
the returned hits by source or by the collision-safe `source#section` parent.

```{code-block} python
:caption: Let one exact paragraph retrieve its section

from mari_components.retrieval import AtomVectorHit, aggregate_atom_hits

parents = aggregate_atom_hits(
    [
        AtomVectorHit(
            atom_id="price", source_id="pricing", section_id="enterprise",
            score=0.92,
        ),
        AtomVectorHit(
            atom_id="sales", source_id="pricing", section_id="enterprise",
            score=0.87,
        ),
        AtomVectorHit(
            atom_id="billing", source_id="billing", section_id="enterprise",
            score=0.81,
        ),
    ],
    weights=(1.0, 0.4, 0.2),
)

assert parents[0].parent_id == "pricing#enterprise"
assert parents[0].score == 0.92 + 0.4 * 0.87
```

The top `len(weights)` unique atom hits contribute. A mean across every atom
would penalize larger sections that contain unrelated material. Mari returns the
contributing atom IDs and scores for inspection.

::: source-block
**Evidence**

[ColBERT late interaction](https://arxiv.org/abs/2004.12832){.paper}[ColBERTv2](https://arxiv.org/abs/2112.01488){.paper}
:::

## Score true multi-vector sections

`MultiVectorSection` can carry title, section, raw atom, and contextual atom
vectors. The encoder remains caller-owned.

```{code-block} python
:caption: Match separate query concepts to separate atoms

from mari_components.retrieval import MultiVectorSection, maxsim_section_score

section = MultiVectorSection(
    source_id="pricing",
    section_id="enterprise",
    title_vector=embed("Enterprise"),
    section_vector=embed(section_text),
    atom_vectors={atom.atom_id: embed(atom.text) for atom in atoms},
    contextual_atom_vectors={
        atom.atom_id: embed(atom.contextual_text) for atom in atoms
    },
)

score = maxsim_section_score(
    [embed("enterprise cost"), embed("included SSO")],
    section,
)
```

For each query vector, exact MaxSim takes its best cosine match among the
section vectors, then averages those maxima. At larger scale, pass each
section's matrix to `build_index`: Mari's existing MUVERA FDE and PolarQuant
path generates ANN candidates, then `search_index` reranks them with exact
MaxSim.

::: source-block
**Evidence**

[ColBERTv2 multi-vector retrieval](https://arxiv.org/abs/2112.01488){.paper}[MUVERA paper](https://arxiv.org/abs/2405.19504){.paper}[Google MUVERA explanation](https://research.google/blog/muvera-making-multi-vector-retrieval-as-fast-as-single-vector-search/){.paper}
:::

## Assemble chunks at query time

```{code-block} python
:caption: Expand a hit to neighboring atoms under a token budget

from mari_components.retrieval import assemble_atom_context

context = assemble_atom_context(
    current_atoms,
    hit_atom_ids=[price_atom.atom_id, sso_atom.atom_id],
    token_counts=token_count_by_atom,
    token_budget=800,
    neighbors=2,
)

for chunk in context.chunks:
    model_context.append(chunk.text)
```

Hits receive budget before their neighbors. The selected retrieval evidence
stays in context. Neighbor selection follows increasing ordinal
distance. Mari deduplicates the result and restores source order inside each
section. Returned chunks include hit IDs and exact token accounting.
Presentation chunks live in the returned value for that query.

::: source-block
**Evidence**

[Anthropic contextual retrieval](https://www.anthropic.com/news/contextual-retrieval){.paper}[Late Chunking](https://arxiv.org/abs/2409.04701){.paper}
:::

## Retain temporal atom versions

`TemporalAtom` adds valid time, transaction time, and embedding identity to an
immutable atom. `active_atoms(versions, at=..., known_at=...)` applies half-open
intervals to answer current and historical questions.

```{code-block} python
:caption: Keep old pricing searchable for historical questions

from datetime import datetime, timezone
from mari_components.documents import TemporalAtom, active_atoms

history = [
    TemporalAtom(
        atom=price_499,
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_to=datetime(2026, 3, 14, tzinfo=timezone.utc),
        recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        embedding_model="embed-v3", embedding_version="2026-02",
    ),
    TemporalAtom(
        atom=price_599,
        valid_from=datetime(2026, 3, 14, tzinfo=timezone.utc),
        recorded_at=datetime(2026, 3, 14, tzinfo=timezone.utc),
        embedding_model="embed-v3", embedding_version="2026-02",
    ),
]

february = active_atoms(history, at=feb_1, known_at=apr_1)
current = active_atoms(history, at=apr_1, known_at=apr_1)
```

Ordinary current retrieval indexes versions whose validity and transaction
intervals contain the query times. History remains available as a separate
view, keeping stale atoms out of present-day results.

::: source-block
**Evidence**

[Temporal knowledge graph survey](https://arxiv.org/abs/2201.08236){.paper}[Graphiti temporal knowledge](https://arxiv.org/abs/2501.13956){.paper}
:::

## Function map

| Function | Important options | Returns |
|---|---|---|
| `semantic_atoms(document, *, maximum_atom_characters=2000, fallback_average_characters=1000)` | Semantic first. CDC fallback for oversized blocks | Stable source-spanned atoms |
| `myers_diff(old, new)` | Arbitrary hashable sequences | Shortest coalesced spans |
| `patience_diff(old, new)` | Unique anchors. Myers fallback | Coalesced stable-anchor spans |
| `align_atoms(old, new, *, algorithm=PATIENCE, modification_threshold=.55)` | Exact hash anchors plus local lexical pairing | Unchanged, inserted, deleted, modified |
| `plan_atom_refresh(alignment, *, rebuild_parent_embeddings_eagerly=False)` | Separates raw/contextual reuse. Lazy or eager parent policy is recorded for the host | Reuse, embed, tombstone, invalidate IDs |
| `aggregate_atom_hits(hits, *, parent="section", weights=(1,.4,.2))` | Top-score aggregation | Ranked parents and contributing atoms |
| `maxsim_section_score(query_vectors, section, *, contextual=True)` | Raw or contextual atoms | Exact late-interaction score |
| `assemble_atom_context(..., token_budget, neighbors=2)` | Hits precede neighbors | Ephemeral source-ordered chunks |
| `active_atoms(versions, *, at, known_at)` | Valid and transaction time | Searchable temporal revisions |
