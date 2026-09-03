[]{#overview}

::: version
mari-components · 0.1.0.dev0
:::

# Mari documentation

Mari is a framework-neutral Python library for building knowledge systems from changing source material. It supplies immutable domain types, connector contracts, synchronization planning, multi-vector, graph, and contradiction retrieval, document self-contradiction validation, rank fusion, memory update plans, topic segmentation, evidence validation, freshness tracking, workflow reuse, trajectory analysis, and verification utilities.

::: legend
Current --- implemented Proposed --- planned, not released
:::

## How to read this page

"Current" sections describe importable code in `mari_components`. "Proposed" sections describe concrete interfaces and algorithms that are not released. Each research-derived mechanism links its evidence next to the explanation; library boundaries and failure behavior are labeled as Mari engineering contracts.

**Package naming**`mari-components` is the distribution. Public imports use `mari_components`.

------------------------------------------------------------------------

[]{#install}

## Install

Python 3.11--3.13 is supported. NumPy is the only runtime dependency.

:::: code
::: code-header
terminal

Copy
:::

    pip install mari-components

    # Optional runtime adapters
    pip install 'mari-components[openai-agents]'
    pip install 'mari-components[langchain]'
::::

### How it works

The base wheel installs the domain, connector, synchronization, retrieval, knowledge, trajectory, and verification modules without a model SDK or database client. Extras add adapter imports only; applications still inject model calls, HTTP transport, persistence, clocks, and authorization decisions. This is package behavior, not a research-derived algorithm.

------------------------------------------------------------------------

[]{#architecture}

## Architecture

Values cross explicit boundaries. Mari plans and validates; the application performs side effects.

:::::::{container} diagram flow
::: card
**Sources**[provider APIs]{.small}
:::

*poll*

::: card
**Documents**[identity · revision · ACL]{.small}
:::

*derive*

::: card
**Knowledge**[facts · answers · decisions]{.small}
:::

*retrieve*

::: card
**Context**[allowed · fresh · cited]{.small}
:::
:::::::

| Mari supplies | Application supplies |
|----|----|
| Typed values and pure planning functions | Database and transactions |
| Connector polling and cursor contracts | Credentials, HTTP transport, retries, scheduler |
| Strict parsers for generated values | Model, prompts, and inference |
| Retrieval and index serialization | Embeddings and index lifecycle |
| Policy and evaluation functions | Authorization and agent runtime |

### How it works

Provider data is normalized into immutable values. Pure functions transform those values into plans, candidates, reports, or index payloads. The caller validates the return value and commits it through its own transaction boundary. Because network and storage operations are injected, the same input values can be replayed in tests before any side effect occurs.

::: source-block
**Research and standards**

[W3C PROV data model](https://www.w3.org/TR/prov-dm/){.paper}[Data pipeline reproducibility](https://arxiv.org/abs/2006.12117){.paper}

[Provenance and reproducibility motivate explicit entities, revisions, activities, and captured configuration. The pure-planning/application-commit split is a Mari engineering contract.]{.small}
:::

------------------------------------------------------------------------

:::{container} chapter current-chapter
**Current API**Available in mari-kit today
:::

[]{#documents}[Current]{.current-label}

## Documents, identity, and ACLs

`KnowledgeDocument` is the canonical provider-owned record. Its stable ID is `{source_id}/{external_id}`. Domain values are frozen dataclasses.

### How it works

`source_id` names one configured source; `external_id` is the provider's stable object key. Their pair prevents two providers from colliding. `revision` identifies content version, while `updated_at` is descriptive metadata and is never used as identity. ACL visibility and principals travel with the document so an allowed-ID set can be computed before retrieval scoring. Frozen values prevent an indexed object from changing behind its recorded revision.

:::: code
::: code-header
document.py

Copy
:::

    from mari_components import DocumentACL, KnowledgeDocument, Principal

    doc = KnowledgeDocument(
        source_id="github:acme/product",
        external_id="file:docs/refunds.md",
        title="Refund policy",
        body="## Enterprise\nRefunds close after 30 days.",
        revision="8f31c2a", updated_at="2026-08-31T10:00:00Z",
        source_url="https://github.com/acme/product/blob/main/docs/refunds.md",
        acl=DocumentACL(visibility="restricted", principals=(
            Principal(kind="team", identifier="support"),
        )),
        metadata={"path": "docs/refunds.md"},
    )
    assert doc.document_id == "github:acme/product/file:docs/refunds.md"
::::

::::::: cards
::: card
`PollPage`

Upserts, tombstones, cursor, checkpoint, snapshot completeness, provider metadata.
:::

::: card
`Tombstone`

Explicit deletion by source and external ID.
:::

::: card
`KnowledgeSection`

Stable section ID, offsets, text, and section revision.
:::

::: card
`Evidence`

Exact quote plus document, revision, span, and optional section coordinates.
:::
:::::::

::: source-block
**Research and standards**

[W3C PROV: entity identity and revision](https://www.w3.org/TR/prov-dm/){.paper}[Zanzibar: relationship-based authorization](https://research.google/pubs/zanzibar-googles-consistent-global-authorization-system/){.paper}

[Mari carries principals and visibility but does not implement an authorization engine. The application resolves those fields to `allowed_document_ids`.]{.small}
:::

------------------------------------------------------------------------

[]{#connectors}[Current]{.current-label}

## Polling and streaming connectors

Every connector defines a frozen configuration object, validation, and polling. GitHub, Slack, Google Drive, and Confluence also accept verified provider events. Network calls use an injected `HttpTransport`.

### How it works

A polling connector starts from the caller's cursor, requests bounded pages, normalizes provider objects, emits explicit tombstones, and returns the next cursor/checkpoint. A streaming connector verifies the raw delivery before parsing it, reduces provider payloads to bounded `ChangeHint` keys, coalesces duplicates, and canonically refetches the object. Both routes produce `PollPage`, so event order, partial webhook payloads, and provider retry behavior cannot bypass synchronization invariants.

::: matrix
GitHubSlackGoogle DriveConfluenceDropboxNotionAirtableAsanaJiraLinearTrelloZendesk
:::

::::::{container} diagram flow
<div>

**Scheduled poll**[PollRequest · cursor · checkpoint]{.small}

</div>

*→*

<div>

**Canonical PollPage**[upserts · tombstones · revision]{.small}

</div>

*→*

<div>

**plan_sync**[one persistence path]{.small}

</div>
::::::

::::::{container} diagram flow
<div>

**Provider stream**[raw body · headers]{.small}

</div>

*verify + parse*

<div>

**ChangeHint**[bounded · coalesced]{.small}

</div>

*canonical refetch*

<div>

**PollPage**[same synchronization path]{.small}

</div>
::::::

### Provider examples

All polling functions accept the same `PollRequest` and injected `HttpTransport`, and return an iterator of `PollPage` values.

::::::::::::::: connector-examples
::: card
#### GitHub

Files, issues, pull requests, and commits.

    from mari_components.connectors import GitHubConfig, poll_github
    cfg = GitHubConfig(token=token, repository="acme/product",
        branch="main", paths=("docs/**",),
        content_types=("files", "issues", "pull_requests"))
    pages = poll_github(cfg, request, http=http)
:::

::: card
#### Slack

Channels, DMs, and canonical thread documents.

    from mari_components.connectors import SlackConfig, poll_slack
    cfg = SlackConfig(bot_token=bot_token,
        history_token=history_token, channels=("C0123",))
    pages = poll_slack(cfg, request, http=http)
:::

::: card
#### Google Drive

Drive files, Google Docs, changes, and push watches.

    from mari_components.connectors import GoogleDriveConfig, poll_google_drive
    cfg = GoogleDriveConfig(access_token=token, folder_id="folder-id")
    pages = poll_google_drive(cfg, request, http=http)
    # poll_google_drive_changes(...) and start_google_drive_watch(...)
:::

::: card
#### Confluence

Cloud pages converted from storage HTML to Markdown-like text.

    from mari_components.connectors import ConfluenceConfig, poll_confluence
    cfg = ConfluenceConfig(site_url="https://acme.atlassian.net/wiki",
        email="bot@acme.com", api_token=token, space_key="ENG")
    pages = poll_confluence(cfg, request, http=http)
:::

::: card
#### Dropbox

Native delta cursor with explicit deleted entries.

    from mari_components.connectors import DropboxConfig, poll_dropbox
    cfg = DropboxConfig(token=token, path="/Knowledge")
    pages = poll_dropbox(cfg, request, http=http)
:::

::: card
#### Notion

Page search and bounded block-tree ingestion.

    from mari_components.connectors import NotionConfig, poll_notion
    cfg = NotionConfig(token=token)
    pages = poll_notion(cfg, request, http=http)
:::

::: card
#### Airtable

Base metadata and table snapshots.

    from mari_components.connectors import AirtableConfig, poll_airtable
    cfg = AirtableConfig(token=token, base_id="appABC123")
    pages = poll_airtable(cfg, request, http=http)
:::

::: card
#### Asana

Workspace or project tasks with offset checkpoints.

    from mari_components.connectors import AsanaConfig, poll_asana
    cfg = AsanaConfig(token=token, workspace_gid="workspace-gid",
        project_gid="project-gid")
    pages = poll_asana(cfg, request, http=http)
:::

::: card
#### Jira

Cloud issues with project or custom JQL scope.

    from mari_components.connectors import JiraConfig, poll_jira
    cfg = JiraConfig(site_url="https://acme.atlassian.net",
        email="bot@acme.com", api_token=token, project_key="SUP")
    pages = poll_jira(cfg, request, http=http)
:::

::: card
#### Linear

Issues and comments through the GraphQL API.

    from mari_components.connectors import LinearConfig, poll_linear
    cfg = LinearConfig(api_key=api_key, team_id="team-id")
    pages = poll_linear(cfg, request, http=http)
:::

::: card
#### Trello

Open boards, lists, and cards.

    from mari_components.connectors import TrelloConfig, poll_trello
    cfg = TrelloConfig(api_key=api_key, token=token)
    pages = poll_trello(cfg, request, http=http)
:::

::: card
#### Zendesk

Guide articles with ordered page checkpoints.

    from mari_components.connectors import ZendeskConfig, poll_zendesk
    cfg = ZendeskConfig(subdomain="acme",
        email="bot@acme.com", api_token=token)
    pages = poll_zendesk(cfg, request, http=http)
:::
:::::::::::::::

:::: code
::: code-header
connector.py

Copy
:::

    from mari_components import PollRequest
    from mari_components.connectors import GitHubConfig, poll_github, validate_github

    config = GitHubConfig(token=token, repository="acme/product",
        paths=("docs/**",), content_types=("files", "issues"))
    validation = validate_github(config, http=http)
    request = PollRequest(cursor=saved_cursor, page_size=100, page_limit=20)

    for page in poll_github(config, request, http=http):
        consume(page)
::::

### Streaming

`stream_pages` requires a verifier, rejects oversized deliveries and batches, parses provider-specific hints, coalesces repeated aggregate keys, and calls an injected hydration function. The application owns the webhook server, queue, acknowledgement, and retries.

:::: code
::: code-header
stream.py

Copy
:::

    from mari_components.connectors import StreamEvent, stream_pages

    event = StreamEvent(provider="slack", raw_body=raw_body, headers=headers)

    def hydrate(hint):
        document, complete = fetch_slack_thread_by_id(config,
            hint.metadata["channel"], hint.metadata["thread_timestamp"], http=http)
        return (PollPage(upserts=(document,) if document else (),
            snapshot_complete=complete),)

    for page in stream_pages((event,), verify=verify_signature, hydrate=hydrate):
        consume(page)
::::

### Connector-specific capabilities

- All twelve connectors: polling, validation, pagination limits, normalized documents, and explicit deletion handling.
- GitHub, Slack, Google Drive, and Confluence: verified streaming change hints plus canonical refetch.
- Slack: canonical thread fetch by ID.
- Google Drive: native Changes polling and push-watch registration.
- Confluence: direct canonical page fetch.
- `ConnectorDefinition.supports(ConnectorMode.POLL | STREAM)` exposes mode capabilities for setup UIs.

::: source-block
**Standards and protocol basis**

[OpenAPI: HTTP operation contracts](https://spec.openapis.org/oas/latest.html){.paper}[CloudEvents: event envelopes](https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md){.paper}[RFC 2104: HMAC verification](https://www.rfc-editor.org/rfc/rfc2104){.paper}

[Provider pagination, cursor, and signature schemes differ. Mari normalizes their observable results; it does not claim a universal delivery guarantee.]{.small}
:::

------------------------------------------------------------------------

[]{#sync}[Current]{.current-label}

## Synchronization

`plan_sync` compares a durable `SyncState` with one `PollPage` and returns a side-effect-free `SyncPlan`. `stream_sync` applies the same rules across pages.

### How it works

For each upsert, Mari validates source ownership and compares a deterministic content fingerprint with the manifest: equal means unchanged; unequal means upsert. Explicit tombstones always become deletes. Absence becomes deletion only after the terminal page of an authoritative full snapshot. The returned plan carries the prior generation as a compare-and-swap precondition and the next manifest/cursor as proposed state; persistence must atomically commit both data and state.

::::::::{container} diagram state
<div>

**Start**[generation 41]{.small}

</div>

*→*

<div>

**Pages**[upsert · tombstone · unchanged]{.small}

</div>

*→*

::: gate
**Complete?**[no: preserve missing docs]{.small}
:::

*→*

<div>

**Reconcile**[yes: absence may delete]{.small}

</div>

*→*

<div>

**Commit**[CAS generation 42]{.small}

</div>
::::::::

:::: code
::: code-header
sync.py

Copy
:::

    from mari_components import SyncMode
    from mari_components.sync import SyncState, plan_sync

    state = load_state() or SyncState()
    for page in provider_pages:
        plan = plan_sync(state, page,
            source_id="github:acme/product", mode=SyncMode.FULL)
        store.commit(upserts=plan.upserts, deletes=plan.deletes,
            state=plan.state, expected_generation=plan.expected_generation)
        state = plan.state
::::

### Enforced invariants

- Page replay is idempotent through content fingerprints and manifests.
- Only terminal, authoritative full pages reconcile absence.
- Explicit tombstones apply in full and incremental modes.
- Incomplete full sync cannot resume as incremental.
- Generation compare-and-swap prevents concurrent state loss.
- Foreign source IDs, duplicate IDs, and upsert/delete overlap are rejected.

::: source-block
**Research basis**

[Build Systems à la Carte: fingerprints and minimal rebuilds](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/03/build-systems.pdf){.paper}[Dynamo: versioning and reconciliation](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf){.paper}

[Snapshot authority, deletion rules, and atomic compare-and-swap are Mari's connector/store contract.]{.small}
:::

------------------------------------------------------------------------

[]{#retrieval}[Current]{.current-label}

## Multi-vector retrieval

Mari implements MUVERA fixed-dimensional candidate generation, PolarQuant compression, and exact normalized MaxSim reranking in one retrieval path.

::::::{container} diagram retrieval
<div>

**Query token vectors**

</div>

*MUVERA*

<div>

**Candidate documents**[allowed IDs only]{.small}

</div>

*exact MaxSim*

<div>

**RetrievalHit\[\]**[ranked + scored]{.small}

</div>
::::::

:::: code
::: code-header
retrieve.py

Copy
:::

    from mari_components.retrieval import FDEConfig, build_index, search_index

    index = build_index({doc.document_id: token_vectors},
        config=FDEConfig(repetitions=20, projection_dimension=16))
    hits = search_index(index, query_token_vectors, limit=8,
        allowed_document_ids=authorized_document_ids)
::::

`serialize_index` and `deserialize_index` use versioned, checksummed payloads. `exact_maxsim` is public for direct scoring.

**Authorization must precede scoring.** Supply `allowed_document_ids`; post-filtering can leak information through ranks and fallback behavior.

### How it works and backing algorithms

Mari\'s current path uses token-level late interaction: each query token takes its maximum similarity to any document token, and the maxima are summed. MUVERA maps those multi-vector sets to fixed-dimensional encodings for fast candidate generation; Mari then reranks the candidates with exact MaxSim. The packed Polar codec is an implementation-level compression of candidate encodings, not an alternative relevance model.

| Status | Index family | Representation and algorithm | Appropriate when | Primary source |
|----|----|----|----|----|
| [Current]{.pill .live} | MUVERA + exact MaxSim | Multi-vector FDE candidate generation, compressed storage, exact late-interaction reranking | Fine-grained semantic matching where individual query terms matter | [MUVERA](https://arxiv.org/abs/2405.19504){.paper} · [ColBERT](https://arxiv.org/abs/2004.12832){.paper} |
| [Proposed]{.pill .next} | Dense flat | Exact cosine, dot-product, or L2 scan over one vector per passage | Small corpora, evaluation baselines, or exact reproducibility | [Dense Passage Retrieval](https://arxiv.org/abs/2004.04906){.paper} |
| [Proposed]{.pill .next} | HNSW | Hierarchical proximity graph for approximate nearest-neighbor search | Large mutable dense-vector collections with low-latency queries | [HNSW](https://doi.org/10.1109/TPAMI.2018.2889473){.paper} |
| [Proposed]{.pill .next} | IVF-PQ | Coarse inverted partitions plus product-quantized vector codes | Memory-constrained or very large dense indexes | [Product Quantization](https://doi.org/10.1109/TPAMI.2010.57){.paper} · [Faiss](https://arxiv.org/abs/1702.08734){.paper} |
| [Proposed]{.pill .next} | BM25 | Probabilistic lexical ranking over an inverted term index | Exact names, identifiers, code symbols, and domain terminology | [BM25 and Beyond](https://doi.org/10.1561/1500000019){.paper} |
| [Proposed]{.pill .next} | Learned sparse | Transformer-produced sparse term weights served by an inverted index | Lexical interpretability with learned expansion | [SPLADE](https://arxiv.org/abs/2107.05720){.paper} |
| [Current]{.pill .live} | Rank fusion | Weighted reciprocal-rank fusion over independent result lists, with per-source contribution traces | Mixed corpora where source scores are not directly comparable | [RAG-Fusion](https://arxiv.org/abs/2402.03367){.paper} |
| [Current]{.pill .live} | Graph propagation | Allowed-node personalized PageRank followed by weighted node-to-passage projection | Multi-hop recall from query-linked entities, facts, or sections | [HippoRAG](https://arxiv.org/abs/2405.14831){.paper} |

### Proposed index interface

The common protocol should describe capabilities rather than a vendor. Index selection then becomes pipeline configuration and can be evaluated against recall, latency, memory, freshness, and ACL-filter behavior.

::::{container} code proposed-code
::: code-header
proposed / indexes.py

Copy
:::

    indexes = {
        "exact": DenseFlatIndex(metric="cosine"),
        "dense": HNSWIndex(metric="cosine", m=32, ef_search=128),
        "compressed": IVFPQIndex(partitions=4096, subquantizers=32),
        "lexical": BM25Index(k1=1.2, b=0.75),
        "sparse": SparseVectorIndex(model="splade"),
        "late": LateInteractionIndex(candidate="muvera", rerank="maxsim"),
    }

    hybrid = HybridIndex(arms=[indexes["lexical"], indexes["dense"], indexes["late"]],
        fusion=ReciprocalRankFusion(k=60))
::::

### Rank fusion, graph recall, and diverse packing

::::::{container} diagram context
::: arms
MUVERAlexicalrecent
:::

*RRF*

<div>

**authorized nodesPageRankpassage projection**

</div>

*MMR*

<div>

**Context candidates**[scores and contributions retained]{.small}

</div>
::::::

:::: code
::: code-header
compose_retrieval.py

Copy
:::

    from mari_components.retrieval import (
        maximal_marginal_relevance, personalized_pagerank,
        project_graph_scores, reciprocal_rank_fusion,
    )

    fused = reciprocal_rank_fusion(
        {"muvera": dense_ids, "lexical": lexical_ids, "recent": recent_ids},
        weights={"recent": 0.25}, rank_constant=60,
        eligible=authorized_document_ids.__contains__, limit=40)

    nodes = personalized_pagerank(graph, query_seeds,
        allowed_node_ids=authorized_graph_nodes, damping=0.85)
    passages = project_graph_scores(nodes.hits, node_passages, limit=20)

    context = maximal_marginal_relevance(
        {hit.document_id: hit.score for hit in fused},
        similarity=passage_similarity, relevance_weight=0.65, limit=12)
    assert nodes.converged
::::

------------------------------------------------------------------------

[]{#contradiction-retrieval}[Current]{.current-label}

## SparseCL contradiction retrieval

Contradiction retrieval asks which corpus passage explicitly disagrees with a query passage. Ordinary similarity alone tends to retrieve paraphrases. SparseCL combines topical cosine similarity with the sparsity of the difference between separately trained embeddings.

### How it works

1.  **Encode twice.** A standard encoder `E` produces similarity vectors; a SparseCL-trained encoder `E_s` produces vectors where contradictions differ in a small semantic subspace.
2.  **Authorize first.** Remove every passage outside `allowed_passage_ids` before computing scores.
3.  **Generate candidates.** Rank allowed passages by `cos(E(q), E(p))` and retain a large configurable candidate set---1,000 in the paper's example.
4.  **Measure sparse difference.** Compute normalized Hoyer sparsity over `E_s(q) − E_s(p)`. One-coordinate differences approach 1; dense differences approach 0.
5.  **Rerank.** Sort by `cosine + alpha × Hoyer`, with stable passage-ID ties, and retain every component in the result trace.

:::::::{container} diagram flow
::: card
**Query + corpus**[authorized passages only]{.small}
:::

*cosine*

::: card
**Top-K candidates**[same-topic prefilter]{.small}
:::

*Hoyer*

::: card
**Sparse rerank**[cos + α · sparsity]{.small}
:::

*→*

::: card
**ContradictionHit\[\]**[components + stable rank]{.small}
:::
:::::::

:::: code
::: code-header
sparsecl.py

Copy
:::

    from mari_components.retrieval import (
        SparseContradictionCandidate, rank_sparse_contradictions,
    )

    hits = rank_sparse_contradictions(
        similarity_encoder(query), sparsecl_encoder(query),
        (SparseContradictionCandidate(
            passage_id=p.id,
            similarity_embedding=similarity_encoder(p.text),
            sparse_embedding=sparsecl_encoder(p.text),
        ) for p in corpus),
        alpha=0.4, candidate_limit=1000, limit=10,
        allowed_passage_ids=authorized_ids,
    )
    for hit in hits:
        audit(hit.cosine_similarity, hit.difference_sparsity, hit.score)
::::

### Training-objective conformance

`sparse_contrastive_losses` evaluates the paper's Hoyer contrastive loss: contradictions are positives, similar non-contradictory passages are hard negatives, and the rest of the batch supplies soft negatives. It is a NumPy conformance oracle, not an autodiff trainer; the application trains `E_s` in PyTorch, JAX, or another framework.

::: source-block
**Paper**

[SparseCL: Sparse Contrastive Learning for Contradiction Retrieval](https://arxiv.org/abs/2406.10746){.paper}

[Mari implements Equations 1--3, cosine prefiltering, sparse reranking, authorization ordering, validation, and score traces. Its Hoyer edge fixtures match the MIT-licensed Overcomplete implementation. The official SparseCL repository has no declared license, so no source from it is incorporated. Mari does not ship the trained encoder.]{.small}
:::

------------------------------------------------------------------------

[]{#document-contradiction}[Current]{.current-label}

## Document-level self-contradiction detection

This is not corpus retrieval. It validates whether one multi-sentence document is judged to contradict itself, where the conflict occurs, how much of the document the reasoning inspected, and how an external reinforcement-learning trainer should score the result.

### How it works

1.  **Tag sentences.** Number the document from 1 through `n` before inference.
2.  **Propose a judgment.** An injected model returns a Boolean judgment, localized evidence sentence IDs, and reasoning containing `[i]`, `[i-j]`, or `[i]-[j]` references.
3.  **Validate localization.** Mari expands ranges, rejects out-of-document references, requires evidence for positive judgments, and forbids contradiction evidence on negative judgments.
4.  **Measure reference coverage.** Deduplicate every sentence mentioned in reasoning and compute `|S_covered| / |S_total|`.
5.  **Compute independent rewards.** Return accuracy, reference-coverage, and format components for an external GRPO trainer. A correct positive judgment without any gold-evidence hit receives `-1`; a correct localized judgment receives `1 + matched/gold`.

:::::::{container} diagram flow
::: card
**Tagged document**[\[1\] ... \[2\] ... \[n\]]{.small}
:::

*model*

::: card
**Judgment + evidence**[reasoning references]{.small}
:::

*validate*

::: card
**Assessment**[localized + coverage]{.small}
:::

*train/evaluate*

::: card
**Reward components**[accuracy · coverage · format]{.small}
:::
:::::::

:::: code
::: code-header
document_contradiction.py

Copy
:::

    from mari_components.verification import (
        document_contradiction_rewards, validate_document_contradiction,
    )

    assessment = validate_document_contradiction(
        sentence_count=len(sentences), judgment=proposal.judgment,
        evidence_sentence_ids=proposal.evidence_sentence_ids,
        reasoning=proposal.reasoning,
    )
    rewards = document_contradiction_rewards(
        assessment, expected_judgment=case.is_self_contradictory,
        gold_evidence_sentence_ids=case.conflicting_sentence_ids,
        format_valid=proposal.matches_required_format,
    )
::::

**What Mari does not claim**Reference coverage measures which sentence tags appeared in reasoning; it does not prove the reasoning is valid. Mari validates and scores a proposed judgment but does not replace the teacher-distilled SFT model, GRPO trainer, or semantic contradiction verifier.

::: source-block
**Papers**

[Reinforced Reference Coverage for Document-Level Self-Contradiction Detection](https://aclanthology.org/2025.emnlp-main.67/){.paper}[ContraDoc benchmark](https://arxiv.org/abs/2311.09182){.paper}

[Mari implements sentence-reference parsing, localization invariants, Equation 7 coverage, and Equations 5--8 reward components. These were checked against the MIT RRC-DSCD implementation and Apache-2.0 ContraDoc boundary. The RRC repository's current accuracy code diverges from published Equation 5: it normalizes by predicted evidence and produces a 0.5 zero-hit score. Mari deliberately retains the paper's gold-normalized term and -1 zero-hit result.]{.small}
:::

------------------------------------------------------------------------

[]{#memory-algorithms}[Current]{.current-label}

## Memory segmentation and mutation plans

`hybrid_topic_segments` splits a stream only where an attention-boundary peak and a semantic-similarity valley agree. The application extracts candidates from those bounded groups and classifies each one as add, update, delete, or no-op. `plan_memory_mutations` validates the decisions without writing storage.

### How it works

Normalize boundary and adjacent-similarity arrays to the `n−1` gaps between `n` turns. A gap is eligible only when its attention score is a local peak above the configured boundary threshold and its adjacent semantic similarity is below the valley threshold. Eligible gaps split consecutive, non-overlapping segments. Mutation planning then requires exactly one decision per candidate, validates update/delete targets against current IDs, rejects duplicate adds and conflicting operations on one target, and returns a deterministic plan.

::::::{container} diagram promotion
<div>

**Turns**[attention + similarity signals]{.small}

</div>

*topic boundary*

<div>

**Candidate memories**[host extraction and classification]{.small}

</div>

*validated plan*

<div>

**Host commit**[ADD · UPDATE · DELETE · NOOP]{.small}

</div>
::::::

:::: code
::: code-header
memory_update.py

Copy
:::

    from mari_components.knowledge import (
        MemoryDecision, MemoryOperation, hybrid_topic_segments,
        plan_memory_mutations,
    )

    segments = hybrid_topic_segments(turns,
        attention_boundaries=attention, adjacent_similarities=similarity,
        similarity_threshold=0.40)

    plan = plan_memory_mutations(existing, candidates, {
        "new-role": MemoryDecision(operation=MemoryOperation.UPDATE,
            target_id="role", reason="newer explicit statement"),
        "unchanged": MemoryDecision(operation=MemoryOperation.NOOP),
    })
    store.commit(plan, expected_generation=generation)
::::

**Classification remains application-owned.**Mari checks candidate coverage, target existence, add collisions, and conflicting target operations. `apply_memory_mutations` provides a pure preview for tests; it is not a database.

::: source-block
**Research basis**

[Mem0: memory extraction and update operations](https://arxiv.org/abs/2504.19413){.paper}[LightMem: topic-aware memory consolidation](https://arxiv.org/abs/2510.18866){.paper}

[The conjunctive peak/valley rule and mutation validation are Mari implementations; model-based classification remains outside the library.]{.small}
:::

------------------------------------------------------------------------

[]{#parsers}[Current]{.current-label}

## Knowledge parsers

Models return JSON-like values. Parsers resolve all evidence against supplied document and section revisions and return immutable typed values. Research establishes each task formulation; Mari implements a deterministic validation boundary rather than the cited model.

### How it works

Each parser first requires the recipe's top-level collection, then validates every required field and enum, resolves evidence through the exact contract below, derives deterministic audit signals, and constructs frozen result types. It never repairs a claim's meaning. Batch claim assessment is the exception to fail-fast parsing: rows are keyed back to caller order, absent rows become `uncertain`, and individually malformed rows do not erase valid siblings.

:::{container} diagram stages
model proposal*→*schema*→*exact evidence*→*revision binding*→*typed candidate
:::

| Parser | Produces | Research-backed task | Academic sources |
|----|----|----|----|
| `parse_facts` | `FactCandidate` | Atomic claims and optional document-level relations with evidence | [FActScore](https://arxiv.org/abs/2305.14251){.paper} · [DocRED](https://arxiv.org/abs/1906.06127){.paper} |
| `parse_claim_assessments` | `FactAssessment` | Supported, contradicted, or uncertain verdicts; decisive rows require evidence | [FEVER](https://arxiv.org/abs/1803.05355){.paper} |
| `parse_decisions` | `DecisionCandidate` | Decision-related utterance extraction without treating topical language as proof | [Hsueh & Moore](https://aclanthology.org/N07-1004/){.paper} · [Karan et al.](https://aclanthology.org/2021.sigdial-1.56/){.paper} |
| `parse_answer` | `GroundedAnswer` | Evidence-selected document QA, citations, or explicit insufficient evidence | [QASPER](https://arxiv.org/abs/2105.03011){.paper} · [ALCE](https://arxiv.org/abs/2305.14627){.paper} |
| `parse_answer_candidates` | `AnswerCandidate[]` | Reusable question-answer pairs bound to supporting passages | [QASPER](https://arxiv.org/abs/2105.03011){.paper} |
| `parse_glossary` | `GlossaryCandidate[]` | Term-definition relations, aliases, and source spans | [DeftEval](https://arxiv.org/abs/2008.13694){.paper} |
| `parse_digest` | `DigestSummary` | Overall and topic summaries with separately inspectable evidence | [QAGS](https://arxiv.org/abs/2004.04228){.paper} · [SummaC](https://arxiv.org/abs/2111.09525){.paper} |
| `parse_impact` | `ImpactAssessment` | In-scope affected-document proposals followed by deterministic dependency checks | Mari contract; no claimed benchmark reproduction |
| `parse_refinement` | `RefinementEdit[]` | Bounded, attribution-aware, fact-preserving edit proposals | [RARR](https://arxiv.org/abs/2210.08726){.paper} · [FactEditor](https://arxiv.org/abs/2007.00916){.paper} |

:::: code
::: code-header
answer.py

Copy
:::

    from mari_components.knowledge import parse_answer

    raw = model(question, documents)
    answer = parse_answer(question, documents, raw)
    print(answer.disposition)         # grounded | insufficient_evidence
    print(answer.grounding_coverage)  # deterministic text coverage
    print(answer.evidence[0].quote)  # exact source text
::::

Additional deterministic helpers include `normalize_claim`, `deduplicate_fact_candidates`, `grounding_coverage`, and `excerpt`. Recoverable batch drift is handled conservatively: assessment rows are restored to caller order, missing rows become uncertain, and good rows survive alongside invalid ones. Structured fact qualifiers preserve subject, relation, object, scope, validity, and conditions.

**`grounding_coverage` is not entailment or confidence.**It is a Mari-specific lexical audit signal motivated by citation completeness. Exact quote validation prevents fabricated citations but does not prove that every paraphrase follows logically from its evidence.

------------------------------------------------------------------------

[]{#evidence}[Current]{.current-label}

## Evidence contracts

An evidence record is a byte-for-byte quotation bound to the exact document and section revision that was supplied to a parser. It is provenance, not a model confidence score.

### How it works

1.  **Restrict the corpus.** Build an allowed map from only the `KnowledgeDocument` values passed by the caller. A model cannot cite an ID outside that map.
2.  **Resolve the document.** Require `document_id`. If exactly one allowed document contains the quote, Mari may recover a missing ID; zero or multiple holders is rejected.
3.  **Match exact text.** Require a non-empty quote and test literal containment in the canonical document body. Fuzzy, normalized, or semantic matches are not accepted.
4.  **Resolve one section.** Split the document into current sections and find sections containing the quote. A repeated quote spanning multiple sections is rejected unless `section_id` selects exactly one.
5.  **Derive coordinates.** Mari computes `start = section.start + section.body.index(quote)` and `end = start + len(quote)`; it does not trust model-supplied offsets or revisions.
6.  **Bind revisions.** The accepted record receives the current `document.revision`, stable `section_id`, and content-derived `section.revision`. These become the invalidation key.

:::::{container} diagram evidence
::: source
[refunds.md · rev 8f31c2a]{.small}

Enterprise refunds close after [30 days]{.mark}.
:::

*literal containment\
+ unique section*

::: record
**Evidence**`document_id = …refunds.md``revision = 8f31c2a``quote = "30 days"``start = 31 · end = 38``section_id = enterprise``section_revision = sha256:…`
:::
:::::

:::: code
::: code-header
evidence.py

Copy
:::

    from mari_components.knowledge import parse_facts

    raw = {"facts": [{
        "claim": "Enterprise refunds close after 30 days.",
        "evidence": [{"document_id": doc.document_id,
                      "section_id": "enterprise",
                      "quote": "30 days"}],
    }]}
    fact = parse_facts([doc], raw)[0]
    e = fact.evidence[0]
    assert doc.body[e.start:e.end] == e.quote

    # Rejected: unknown document, absent quote, or a repeated quote
    # whose section cannot be selected unambiguously.
::::

### Dependency conversion

`evidence_dependencies` projects each record to `(document_id, document_revision, section_id, section_revision)`, deduplicated by `(document_id, section_id)` and returned in stable order. Two records naming different revisions of the same key raise `ValueError`; silently choosing one would make reuse nondeterministic.

**What this proves---and does not prove**The contract proves that the quoted characters occurred in one supplied source revision and records where. It does not prove entailment, source authority, completeness, or truth. Those require claim assessment, corroboration, authorization, and review.

::: source-block
**Research and standards**

[ALCE: citation correctness and completeness](https://arxiv.org/abs/2305.14627){.paper}[QASPER: evidence-bearing document QA](https://arxiv.org/abs/2105.03011){.paper}[FActScore: atomic factual claims](https://arxiv.org/abs/2305.14251){.paper}[FEVER: evidence-backed verdicts](https://arxiv.org/abs/1803.05355){.paper}[W3C PROV: quotation, derivation, and revision](https://www.w3.org/TR/prov-dm/){.paper}

[These works motivate inspectable evidence and revision provenance. Literal substring validation, unique-section resolution, and failure behavior are Mari engineering contracts.]{.small}
:::

------------------------------------------------------------------------

[]{#freshness}[Current]{.current-label}

## Freshness and impact

Freshness is an exact dependency comparison. It answers "did an input revision change?"---not "is the answer still semantically correct?"

### How it works

1.  **Record dependencies.** Every derived artifact stores the document or section revision used to build it.
2.  **Select comparison granularity.** If a dependency names a section and the caller supplies a section-revision map, compare section hashes. Otherwise compare the containing document revision as a conservative fallback.
3.  **Classify every key.** Missing document/section → `missing`; empty expected/current revision → `unversioned`; unequal revisions → `stale`; otherwise → `current`.
4.  **Reduce deterministically.** Overall precedence is `missing > unversioned > stale > current`. Changes and IDs are sorted, so the same inputs produce the same report.
5.  **Propagate impact.** `impacted_artifacts` evaluates each artifact independently and returns only non-current artifacts. Mari reports the set; the application chooses whether to regenerate, review, or retire them.

::::::{container} diagram dependency
<div>

**Policy answer**[depends on § window]{.small}

</div>

![](data:image/svg+xml;base64,PHN2ZyB2aWV3Ym94PSIwIDAgMTIwIDQwIj48cGF0aCBkPSJNMCAyMCBDNDUgMjAgNzUgMjAgMTIwIDIwIiAvPjwvc3ZnPg==)

::: changed
**§ window**[30 → 45 days]{.small}
:::

![](data:image/svg+xml;base64,PHN2ZyB2aWV3Ym94PSIwIDAgMTIwIDQwIj48cGF0aCBkPSJNMCAyMCBDNDUgMjAgNzUgMjAgMTIwIDIwIiAvPjwvc3ZnPg==)

<div>

**Refresh queue**[only affected artifacts]{.small}

</div>
::::::

:::{container} status-order
[**1 · missing**[source or section absent]{.small}]{.missing}[**2 · unversioned**[cannot compare safely]{.small}]{.unversioned}[**3 · stale**[revision differs]{.small}]{.stale}[**4 · current**[all revisions equal]{.small}]{.current}
:::

:::: code
::: code-header
freshness.py

Copy
:::

    from mari_components.knowledge import (
        FreshnessStatus, assess_dependencies, assess_freshness,
        impacted_artifacts,
    )

    report = assess_freshness(answer.evidence, current_revisions,
        current_section_revisions=current_sections)
    if not report.reusable:
        refresh(report.changes, report.missing_dependency_ids)

    stale = impacted_artifacts(dependencies_by_artifact, current_revisions,
        current_section_revisions=current_sections)
::::

### Document edit versus affected section

:::: code
::: code-header
granularity.py

Copy
:::

    # The document changed v1 → v2, but the cited section is still s1.
    current_revisions = {doc_id: "v2"}
    current_sections = {(doc_id, "refund-window"): "s1"}

    fine = assess_dependencies(deps, current_revisions,
        current_section_revisions=current_sections)
    assert fine.status == FreshnessStatus.CURRENT

    coarse = assess_dependencies(deps, current_revisions)
    assert coarse.status == FreshnessStatus.STALE  # safe fallback
::::

**Operational consequence**Section hashes avoid regenerating an answer when an unrelated section changed. Omitting the section map intentionally increases false-positive refreshes rather than risking stale reuse. Only `current` sets `report.reusable` to true.

::: source-block
**Research and standards**

[Build Systems à la Carte: dependency-driven recomputation](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/03/build-systems.pdf){.paper}[RAG: updateable non-parametric knowledge and provenance](https://arxiv.org/abs/2005.11401){.paper}[W3C PROV: revision and derivation](https://www.w3.org/TR/prov-dm/){.paper}

[Mari applies build-system invalidation to knowledge artifacts. Status precedence, section fallback, and reuse policy are explicit Mari contracts, not semantic change detection.]{.small}
:::

------------------------------------------------------------------------

[]{#sections}[Current]{.current-label}

## Sections and incremental fact scans

`document_sections` maps Markdown headings to stable section IDs and content revisions. `section_revisions` builds the current revision map. Fact scans can then skip unchanged sections.

### How it works

Scan Markdown heading lines, treating content before the first heading as a preamble. Normalize each heading into a slug and suffix collisions deterministically. Store absolute body offsets and hash the section body into its revision. `pending_fact_sections` compares `(document_id, section_id) → revision` with the last committed scan and yields new or changed sections only. Persist new scan revisions only after extracted facts commit, or a failed run would incorrectly suppress retry.

:::: code
::: code-header
fact_scan.py

Copy
:::

    from mari_components.knowledge import (
        document_sections, fact_scan_revisions, pending_fact_sections,
    )

    sections = document_sections(document)
    pending = pending_fact_sections([document], previous_scan_revisions)
    facts = [parse_facts([document], model(section.body)) for section in pending]
    next_revisions = fact_scan_revisions(pending)  # persist only after facts commit
::::

::: source-block
**Research and standards**

[Build Systems à la Carte: change detection and recomputation](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/03/build-systems.pdf){.paper}[RFC 6920: digest-based content identity](https://www.rfc-editor.org/rfc/rfc6920){.paper}

[Markdown heading segmentation and slug collision rules are Mari engineering contracts.]{.small}
:::

------------------------------------------------------------------------

[]{#tags}[Current]{.current-label}

## Tags and links

::::: split
::: card
### Managed tags

`TagDefinition`, `TagAssignments`, `assign_tags`, `normalize_tag`, and `search_weight` keep curation separate from provider-owned documents, so resync does not erase it.
:::

::: card
### Derived links

`extract_explicit_links` finds explicit references. `derive_links` adds bounded similarity links and produces typed `LinkCandidate` values.
:::
:::::

### How it works

Tag keys are normalized before add/remove set operations; definitions validate that assignments refer to known tags. Search weight combines assigned tag weights through deterministic policy rather than rewriting source relevance. Explicit-link extraction recognizes source references first. Similarity linking scores only caller-supplied candidate IDs, removes self-links, applies a threshold and limit, and sorts ties stably. Returned links are proposals; committing and interpreting them remains application policy.

:::: code
::: code-header
curation.py

Copy
:::

    from mari_components.knowledge import (
        TagAssignments, TagDefinition, assign_tags, derive_links, search_weight,
    )

    definitions = {"canonical": TagDefinition(key="canonical", label="Canonical",
        kind="canonical", search_weight=2.0, behaviors=("Wins conflicts",))}
    assignments = assign_tags(TagAssignments(), doc.document_id, definitions,
        add=("canonical",))
    weight = search_weight(doc.document_id, assignments, definitions)
    links = derive_links(doc.document_id, candidate_ids,
        score=lambda source, target: similarity_scores[source, target])
::::

::: source-block
**Research basis**

[Similarity measures for text processing](https://doi.org/10.1145/956863.956972){.paper}[A-MEM: dynamic linked-note organization](https://arxiv.org/abs/2502.12110){.paper}

[Mari's managed-tag overlay and bounded link proposal rules are deterministic curation contracts.]{.small}
:::

------------------------------------------------------------------------

[]{#workflows}[Current]{.current-label}

## Reviewed workflows and cached answers

Reviewed workflow indexes match new requests to approved intents. Policy thresholds independently control speculative retrieval and direct cached-response reuse.

### How it works

Build an index from reviewed workflow intent vectors. At query time, compute normalized similarity, retain only workflows whose dependencies are authorized, and choose the best match with stable ties. Crossing the lower threshold may start retrieval speculatively; crossing the higher threshold only makes reuse eligible. A cached response is returned only after its exact evidence dependencies pass freshness checks. Similarity never overrides ACL or revision failure.

:::::::{container} diagram thresholds
<div>

**0.00**[run normally]{.small}

</div>

::: retr
**0.72**[start retrieval]{.small}
:::

::: reuse
**0.95**[consider reuse]{.small}
:::

<div>

**1.00**

</div>
:::::::

:::: code
::: code-header
workflow.py

Copy
:::

    from mari_components.trajectories import (
        WorkflowPolicy, build_reviewed_workflow_index, decide_reviewed_workflow,
    )

    index = build_reviewed_workflow_index(reviewed_workflows)
    decision = decide_reviewed_workflow(query_vectors, index, current_revisions,
        policy=WorkflowPolicy(speculation_threshold=0.72, cache_threshold=0.95),
        allowed_document_ids=authorized_document_ids)
::::

Related APIs: `match_reviewed_workflow`, `start_speculative_retrieval`, `match_cached_response`, and `workflow_freshness`. Reuse requires a strong match plus fresh, authorized dependencies.

::: source-block
**Research basis**

[GPTCache: semantic caching for language-model queries](https://aclanthology.org/2023.nlposs-1.24/){.paper}[Build Systems à la Carte: dependency-valid reuse](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/03/build-systems.pdf){.paper}

[The two thresholds, authorization gate, and exact freshness condition are Mari policy.]{.small}
:::

------------------------------------------------------------------------

[]{#trajectories}[Current]{.current-label}

## Trajectories and agent evaluation

`normalize_steps` converts runtime records into privacy-bounded `TrajectoryStep` values. `parse_trajectory_analysis` validates model-proposed phases. Mari provides adapters, not an agent loop.

### How it works

Adapters map framework events into ordered `AgentEvent` values. Normalization assigns stable step positions, keeps allowlisted metadata, and redacts sensitive argument names and transport fields. Tool evaluation compares observed names and counts against expectations; outcome evaluation compares terminal paths and completion. A proposed phase analysis must cover every observed event exactly once with contiguous, non-overlapping ranges and known tool families.

::::::{container} diagram timeline
<div>

**inspect**[search_knowledge]{.small}

</div>

<div>

**reason**[2 docs · 2 citations]{.small}

</div>

<div>

**answer**[outcome: resolved]{.small}

</div>
::::::

:::: code
::: code-header
agents.py

Copy
:::

    from mari_components.agents import evaluate_outcome, evaluate_tools
    from mari_components.trajectories import normalize_steps

    steps = normalize_steps(runtime_events)
    tools = evaluate_tools(events, expected_tools=("search_knowledge",))
    outcome = evaluate_outcome(paths=("resolved",),
        expected_paths=("resolved",), completed=True)
::::

`AgentEvent` and `EventKind` are framework-neutral. Optional adapters cover OpenAI Agents and LangChain/LangGraph. Normalization redacts common sensitive arguments; phase validation requires the returned ranges to cover observed events exactly.

:::: code
::: code-header
trajectory_analysis.py

Copy
:::

    from mari_components.trajectories import parse_trajectory_analysis

    analysis = parse_trajectory_analysis(normalized_events, model_labels,
        family_map={"search_product_knowledge": "inspect",
                    "answer": "answer"})
::::

::: source-block
**Research and standards**

[AgentBench: multi-environment agent evaluation](https://arxiv.org/abs/2308.03688){.paper}[OpenTelemetry trace specification](https://opentelemetry.io/docs/specs/otel/trace/){.paper}

[Mari's event schema, redaction list, exact phase coverage, and outcome predicates are library contracts.]{.small}
:::

------------------------------------------------------------------------

[]{#verification}[Current]{.current-label}

## Verification portfolios

Verification functions score already-parsed values and retain all successful attempts and failures for audit.

### How it works

`best_of_n` calls the producer up to `n` times, parses each output, records parse failures without discarding successful siblings, scores valid candidates, and selects the highest score with stable first-wins ties; it may stop once the threshold is met. `verdict_consensus` counts typed verdicts rather than free text. Grounding scores combine declared deterministic components; they are used for ranking or abstention, never calibrated as probabilities.

:::: code
::: code-header
verify.py

Copy
:::

    from mari_components.verification import best_of_n, score_grounded

    result = best_of_n(
        lambda: model(question, documents),
        lambda raw: parse_answer(question, documents, raw),
        lambda answer: score_grounded(answer,
            required_ideas=("eligibility", "time limit")),
        attempts=3, threshold=0.90)

    audit(result.selected, result.attempts, result.failures, result.stopped_early)
::::

:::::::: cards
::: card
`select_best`

Scores existing candidates with stable tie-breaking.
:::

::: card
`verdict_consensus`

Aggregates supported, contradicted, and uncertain assessments.
:::

::: card
`score_grounded`

Evidence, coverage, completeness, corroboration, certainty.
:::

::: card
`harmonic_score`
:::

::: card
`idea_completeness`
:::
::::::::

**Scores are not truth probabilities.**They are deterministic quality signals for selection and abstention.

::: source-block
**Research basis**

[Self-consistency improves chain-of-thought reasoning](https://arxiv.org/abs/2203.11171){.paper}[FEVER: evidence-based verification](https://arxiv.org/abs/1803.05355){.paper}[ALCE: citation quality evaluation](https://arxiv.org/abs/2305.14627){.paper}

[Mari exposes an auditable selection portfolio; it does not reproduce model sampling or benchmark metrics.]{.small}
:::

------------------------------------------------------------------------

[]{#errors}[Current]{.current-label}

## Errors and deliberate boundaries

### How it works

Exceptions classify which boundary failed and whether repeating the same request can help. Connector adapters translate provider responses into authentication, transient, or permanent failures. Snapshot validation raises `IncompleteSnapshot` before absence can become deletion. Knowledge parsers raise `MalformedModelOutput` before an invalid value crosses into typed state. Mari never retries automatically because retry budgets, clocks, credentials, and side effects belong to the host.

| Error | Meaning | Typical handling |
|----|----|----|
| `AuthenticationFailure` | Credentials rejected | Request new credentials |
| `TransientFailure` | Temporary provider failure | Retry using app policy |
| `PermanentFailure` | Request cannot succeed unchanged | Require intervention |
| `IncompleteSnapshot` | Listing is not authoritative | Do not infer deletion |
| `MalformedModelOutput` | Generated value violates parser contract | Retry or abstain |

### Safe representations and connector contracts

Credentials are excluded from connector configuration representations. `HttpRequest` representations redact authorization headers, bodies, URL userinfo, and common sensitive query parameters. `check_connector_contract` provides an executable contract check for third-party connector implementations.

:::: code
::: code-header
connector_test.py

Copy
:::

    from mari_components import SyncMode
    from mari_components.testing import check_connector_contract

    pages = tuple(my_connector(config, request, http=fake_http))
    report = check_connector_contract(pages, mode=SyncMode.FULL,
        starting_cursor=request.cursor)
    assert report.pages == len(pages)
::::

Not included: model client, prompt framework, database, scheduler, credential store, authorization engine, agent runtime, or worker queue.

**Engineering contract**This taxonomy defines control flow and safe defaults. It is not a claim that provider APIs share identical failure semantics; each adapter must map its protocol into these categories and pass the connector contract checks.

------------------------------------------------------------------------

:::{container} chapter proposed-chapter
**Research-backed components and further design**Each section labels current implementation separately from proposed interfaces
:::

[]{#retrieval-construction}[Current]{.current-label}

## Hypothetical and hierarchical retrieval

These functions construct alternative query representations and bounded navigation structures. Generation, encoding, clustering, summarization, and relevance models are injected; Mari owns shape validation, deterministic IDs, budgets, and traces.

### How it works

`hypothetical_document_embedding` weights and averages caller-encoded hypothetical answers, then L2-normalizes the vector used for retrieval; generated text is never stored as fact. `build_summary_tree` repeatedly validates a caller-proposed partition of every current root, creates stable parent nodes, and stops when the root count no longer decreases. `walk_summary_tree` expands the highest-scoring children under explicit branch and visit budgets and returns visited paths plus exhaustion state.

::: source-block
**Papers**

[HyDE: hypothetical document embeddings](https://arxiv.org/abs/2212.10496){.paper}[RAPTOR: recursive summary trees](https://arxiv.org/abs/2401.18059){.paper}[MemWalker: bounded memory-tree navigation](https://arxiv.org/abs/2310.05029){.paper}
:::

::::::::{container} diagram flow
::: card
**Generate**[hypothetical answer]{.small}
:::

*→*

::: card
**Encode**[normalized query vector]{.small}
:::

*→*

::: card
**Retrieve**[candidate sections]{.small}
:::

*→*

::: card
**Organize**[recursive clusters]{.small}
:::

*→*

::: card
**Walk**[branch + visit budget]{.small}
:::
::::::::

### Paper-derived retrieval construction

:::: code
::: code-header
hyde_raptor_memwalker.py · current

Copy
:::

    from mari_components.retrieval import (
        build_summary_tree, hypothetical_document_embedding, walk_summary_tree,
    )

    hyde_vector = hypothetical_document_embedding([
        document_encoder(text) for text in generate_hypotheses(query)
    ])

    tree = build_summary_tree(section_text_by_id,
        cluster=lambda nodes, level: cluster_embeddings(nodes, level),
        summarize=lambda children, level: summarize(children, level))
    walk = walk_summary_tree(tree, lambda node: similarity(query, node.text),
        branch_factor=2, max_visits=24)
    sections = document_store.get_many(walk.leaf_ids)
::::

------------------------------------------------------------------------

[]{#adaptive-retrieval}[Current]{.current-label}

## Adaptive retrieval and compression

Retrieval can be triggered, corrected, rescored, or compressed at explicit decision points instead of running as one opaque model call.

### How it works

CRAG routing maps evaluator scores through two thresholds to use the corpus, augment it with external search, or replace it. FLARE finds low-confidence tokens in a predicted future sentence, removes those tokens, and uses the remaining text as a retrieval query before regeneration. Self-RAG combines generation, retrieval, relevance, support, and utility signals with visible weights. RECOMP selects scored sentences under a token budget, then restores their source order.

::: source-block
**Papers**

[Self-RAG: reflection-token scoring](https://arxiv.org/abs/2310.11511){.paper}[CRAG: corrective retrieval](https://arxiv.org/abs/2401.15884){.paper}[FLARE: forward-looking active retrieval](https://arxiv.org/abs/2305.06983){.paper}[RECOMP: selective compression](https://arxiv.org/abs/2310.04408){.paper}
:::

:::: code
::: code-header
adaptive_retrieval.py · current

Copy
:::

    from mari_components.retrieval import (
        CompressionSentence, plan_active_retrieval, plan_corrective_retrieval,
        selective_compression,
    )
    from mari_components.verification import score_self_rag_candidate

    correction = plan_corrective_retrieval(retrieval_evaluator(query, hits),
        lower_threshold=-0.8, upper_threshold=0.6)
    active = plan_active_retrieval(future.tokens, future.probabilities, threshold=0.2)
    reflection = score_self_rag_candidate(generation_probability=signals.generation,
        retrieve_probability=signals.retrieve, relevance_probability=signals.relevant,
        support_probability=signals.supported, utility=signals.utility)

    compressed = selective_compression([
        CompressionSentence(sentence_id=s.id, text=s.text, token_count=count_tokens(s.text),
            relevance=compressor.score(query, s.text)) for s in sentences
    ], token_budget=600, relevance_threshold=0.4)
::::

------------------------------------------------------------------------

[]{#memory-organization}[Current]{.current-label}

## Memory organization and evidence notes

These functions link related notes, rank memories for recall, and decide whether retrieved evidence can support an answer.

### How it works

Note evolution applies a link threshold and a stricter metadata-evolution threshold to caller-supplied similarities. Salience exponentially decays recency, min-max normalizes recency, importance, and relevance over the candidate set, then returns every weighted contribution. Evidence-note decisions validate per-document relevance and answer support before choosing retrieved evidence, explicitly allowed parametric knowledge, or `unknown`.

::: source-block
**Papers**

[A-MEM: dynamic note evolution](https://arxiv.org/abs/2502.12110){.paper}[Generative Agents: recency, importance, and relevance](https://arxiv.org/abs/2304.03442){.paper}[Chain-of-Note: sequential evidence decisions](https://arxiv.org/abs/2311.09210){.paper}
:::

:::: code
::: code-header
memory_evidence.py · current

Copy
:::

    from mari_components.knowledge import (
        MemorySignal, plan_note_evolution, rank_salient_memories,
    )
    from mari_components.verification import (
        EvidenceNote, decide_from_evidence_notes,
    )

    evolution = plan_note_evolution(new_note.id, similarity_by_note_id,
        link_threshold=0.72, evolution_threshold=0.91)
    salient = rank_salient_memories([
        MemorySignal(memory_id=m.id, hours_since_access=hours_since(m.last_accessed),
            importance=importance(m), relevance=relevance(query, m)) for m in memories
    ], recency_decay=0.995, limit=20)
    decision = decide_from_evidence_notes([
        EvidenceNote(document_id=n.document_id, relevant=n.relevant,
            supports_answer=n.supports_answer) for n in model_notes
    ])
::::

------------------------------------------------------------------------

[]{#admission}[Proposed]{.proposed-label}

## Knowledge admission and mutation planning

Admission is evaluated before reconciliation. A candidate may be valid JSON and still be unsafe, low-authority, redundant, or unsupported. Reconciliation runs only for accepted candidates.

### How it works

Run provenance, evidence-span, recalled-input, secret, external-instruction, authority, and confidence rules over the candidate. Aggregate rule results into `ACCEPT`, `DEFER`, `REJECT`, or `QUARANTINE` with reason codes. Only accepted candidates reach mutation reconciliation, which validates add, merge, supersede, retract, or unchanged operations against the current canonical slot without writing storage.

::: source-block
**Papers and standards**

[Indirect prompt injection](https://arxiv.org/abs/2302.12173){.paper}[W3C PROV](https://www.w3.org/TR/prov-overview/){.paper}[Mem0: memory mutation operations](https://arxiv.org/abs/2504.19413){.paper}

[Disposition precedence and commit boundaries are proposed Mari contracts.]{.small}
:::

::::{container} code proposed-code
::: code-header
proposed / write_plan.py

Copy
:::

    candidate = extractor.propose(observation)
    admission = admit(candidate,
        rules=[RequireEvidenceSpan(), RejectRecalledInput(), QuarantineSecrets(),
               QuarantineExternalInstructions(), EnforceSourceAuthority()],
        thresholds=AdmissionThresholds(accept=0.90, defer=0.65))

    match admission.disposition:
        case ACCEPT:
            mutation = reconcile(candidate, current=artifact_store.canonical_slot(candidate))
            # ADD | MERGE | SUPERSEDE | RETRACT | UNCHANGED
        case DEFER: review_queue.put(candidate, admission.reasons)
        case QUARANTINE: quarantine.put(candidate, admission.reasons)
        case REJECT: audit.record(admission)
::::

------------------------------------------------------------------------

[]{#entity-resolution}[Proposed]{.proposed-label}

## Entity resolution with explicit uncertainty

The cascade spends expensive work only after cheap deterministic checks. It never converts an ambiguous candidate into a merge without a configured threshold or review decision.

### How it works

Block candidates by tenant, scope, and entity type; compare normalized exact aliases; calculate field-agreement and fuzzy scores; retrieve a small embedding neighborhood only for unresolved candidates; then apply separate link and review thresholds. Scores above link become a proposed canonical ID, scores in the review band retain all candidates and their feature trace, and lower scores remain distinct entities.

::: source-block
**Papers**

[Fellegi--Sunter: probabilistic record linkage](https://doi.org/10.1080/01621459.1969.10501049){.paper}
:::

:::{container} diagram resolution-cascade
scope + type block*→*normalized exact*→*field/fuzzy score*→*embedding candidates*→*link · reject · review
:::

::::{container} code proposed-code
::: code-header
proposed / resolve.py

Copy
:::

    resolver = EntityResolver([
        ScopeAndTypeBlock(), NormalizedAliasMatch(),
        ProbabilisticFieldMatch(link=0.95, review=0.72),
        EmbeddingCandidates(index=entity_index, limit=10),
    ])
    resolution = resolver.resolve(candidate, scope=artifact.scope)
    if resolution.ambiguous:
        review_queue.put(resolution.candidates, resolution.comparison_trace)
::::

------------------------------------------------------------------------

[]{#graph-processing}[Current and proposed]{.proposed-label}

## Graph recall and corpus aggregation

Passage retrieval and corpus summarization are different operations. Personalized PageRank is a current bounded multi-hop recall function. Leiden communities and map-reduce reports are proposed, separately versioned aggregation stages.

### How it works

Link query mentions to authorized seed nodes, induce an allowed subgraph, and propagate Personalized PageRank mass until tolerance or iteration limits; project node mass back to evidence-bearing sections. Separately, Leiden partitions the graph into well-connected communities, recursive grouping forms levels, and evidence-linked community reports support global map-reduce queries. Local queries fan out from entities; drift queries start globally and open bounded local branches.

::: source-block
**Papers**

[HippoRAG: Personalized PageRank recall](https://arxiv.org/abs/2405.14831){.paper}[Leiden community detection](https://doi.org/10.1038/s41598-019-41695-z){.paper}[GraphRAG: community reports and global query](https://arxiv.org/abs/2404.16130){.paper}
:::

::::{container} code proposed-code
::: code-header
proposed / graph_algorithms.py

Copy
:::

    recall = PersonalizedPageRank(
        seeds=link_query(query, entities, facts), damping=0.50, hops=3,
        edge_filter=AuthorizedAt(scope=user.scope, at=query.time),
        project_to="source_sections")

    communities = HierarchicalLeiden(resolution=1.0, max_size=40).fit(graph)
    reports = summarize_communities(communities, evidence_policy=ExactEvidence())

    answer = query_corpus(query, mode="global", reports=reports,
        reduction=RatedMapReduce(max_partial_answers=24))
::::

------------------------------------------------------------------------

[]{#consolidation}[Partially current]{.proposed-label}

## Tiered memory consolidation

Tiers are policies over cost and lifecycle, not hard-coded stores. Topic segmentation is current; compression, promotion, and offline scheduling are proposed. Each promotion creates a dependency-bearing proposal, and raw observations remain available for audit.

### How it works

Filter observations cheaply, group them at attention-peak/similarity-valley topic boundaries, compress within bounded groups, and score promotion from recurrence, recency, usefulness, and evidence diversity. Expensive resolving, superseding, and summarization run in an offline call/token budget. Promotion creates a new artifact revision linked to every contributing observation.

::: source-block
**Papers**

[LightMem: topic-aware consolidation and offline updates](https://arxiv.org/abs/2510.18866){.paper}[MemoryOS: tiered agent memory](https://arxiv.org/abs/2506.06326){.paper}
:::

::::::{container} diagram promotion
<div>

**Observation buffer**[cheap filters · content hashes]{.small}

</div>

*topic boundary*

<div>

**Session groups**[bounded compression]{.small}

</div>

*offline window*

<div>

**Consolidated artifacts**[resolve · supersede · review]{.small}

</div>
::::::

::::{container} code proposed-code
::: code-header
proposed / consolidation.py

Copy
:::

    policy = ConsolidationPolicy(
        segment=TopicBoundary(window=12, threshold=0.68),
        promote=PromotionScore(recurrence=0.30, recency=0.15,
            usefulness=0.35, evidence_diversity=0.20),
        schedule=OfflineWindow(max_model_calls=20, max_tokens=50000))
    plan = plan_consolidation(observations, policy=policy)
    commit(review(plan.mutations), dependencies=plan.dependencies)
::::

------------------------------------------------------------------------

[]{#projections}[Proposed]{.proposed-label}

## Event sourcing and disposable projections

Canonical artifacts and append-only events remain authoritative. Search indexes, backlink tables, graph views, digests, and human-readable logs are projections with explicit build identities and safe swap semantics.

### How it works

Append a validated event with an expected generation, fold ordered events through a deterministic projector into a staging version, and record schema plus embedding/configuration fingerprints. Validate counts, checksums, scope isolation, and sample queries before atomically switching the current pointer. A failed replay never replaces the last valid projection, and retaining the prior pointer makes rollback constant-time.

::: source-block
**Papers and standards**

[Data pipeline reproducibility](https://arxiv.org/abs/2006.12117){.paper}[Invariant confluence](https://arxiv.org/abs/1402.2237){.paper}[W3C PROV](https://www.w3.org/TR/prov-overview/){.paper}
:::

::::::{container} diagram projection-flow
<div>

**Canonical artifacts**[documents · events · reviews]{.small}

</div>

*deterministic fold*

<div>

**Staging projections**[vector · lexical · graph · Markdown]{.small}

</div>

*validate + swap*

<div>

**Current read version**[rollback pointer retained]{.small}

</div>
::::::

::::{container} code proposed-code
::: code-header
proposed / projections.py

Copy
:::

    events.append(KnowledgeEvent(kind="artifact.superseded", payload=mutation,
        actor=reviewer, expected_generation=41))

    build = rebuild_projection(events, projector=SearchProjector(
        embedding_identity=embedder.fingerprint(), schema_version="3"))
    validate(build, checks=[DocumentCount(), Checksums(), ScopeIsolation(), SampleQueries()])
    projections.atomic_swap(build, retain_previous=True)

    # A failed build never replaces the last valid read version.
::::

------------------------------------------------------------------------

[]{#procedural-learning}[Proposed]{.proposed-label}

## Procedural learning and regression gates

Execution feedback can propose procedural updates, but promotion depends on held-out cases, negative outcomes, cross-procedure interference, and explicit review.

### How it works

Reflect over a trajectory and observed outcome, turn the reflection into atomic add/update/tag/remove operations, and apply the patch to a copy of the active skillbook. Evaluate that candidate on its own cases, related-procedure cases, and known failures. Hard gates reject grounding or ACL regressions; passing creates a review proposal rather than activating it automatically. Worked, failed, and partial attempts remain separately retrievable.

::: source-block
**Papers**

[Agentic Context Engineering: incremental skillbooks](https://arxiv.org/abs/2510.04618){.paper}[Reflexion: learning from verbal feedback](https://arxiv.org/abs/2303.11366){.paper}[LongMemEval: long-horizon memory evaluation](https://arxiv.org/abs/2410.10813){.paper}
:::

::::{container} code proposed-code
::: code-header
proposed / skillbook.py

Copy
:::

    reflection = reflect(trajectory, outcome=outcome, evidence=observed_context)
    patch = curate(reflection, operations={"ADD", "UPDATE", "TAG", "REMOVE"})
    candidate = skillbook.apply_to_copy(patch)

    gate = regression_gate(candidate, baseline=skillbook.active,
        suites=[own_cases, related_procedure_cases, known_failures],
        require={TaskSuccess(): NoRegression(), Groundedness(): AtLeast(0.95),
                 ACLLeakage(): Exactly(0.0)})
    if gate.passed:
            skillbook.propose(candidate, trace=gate.trace)  # human promotion remains explicit
::::

------------------------------------------------------------------------

[]{#memory-evaluation}[Proposed]{.proposed-label}

## Long-horizon memory evaluation

A memory system needs separate measurements for writing, updating, retrieving, temporal reasoning, abstaining, and respecting context limits. One aggregate answer score hides which subsystem failed.

### How it works

Freeze conversations, source revisions, expected evidence, and change events into cases. Replay each case under several corpus sizes and context budgets. Score extraction at write time, evidence recall at query time, cross-session synthesis, ordering and date reasoning, correction after source updates, abstention when evidence is absent, and ACL leakage. Store per-stage traces with every score so a regression points to the responsible parser, index, policy, or packing decision.

::::::::: metric-grid
<div>

**Extraction**precision · recall · evidence

</div>

<div>

**Retrieval**recall@k · rank · authorization

</div>

<div>

**Synthesis**support · completeness

</div>

<div>

**Temporal**order · valid time · updates

</div>

<div>

**Abstention**unsupported-answer rate

</div>

<div>

**Operations**tokens · latency · refresh work

</div>
:::::::::

::::{container} code proposed-code
::: code-header
proposed / memory_eval.py

Copy
:::

    report = evaluate_memory_system(system, cases,
        corpus_sizes=(100, 10_000, 1_000_000),
        context_budgets=(2_000, 8_000, 32_000),
        metrics=[ExtractionF1(), EvidenceRecall(k=10), UpdateFidelity(),
                 TemporalAccuracy(), AbstentionPrecision(), ACLLeakage()])

    report.by_capability["updates"]
    report.failures  # case, stage, revisions, trace, observed output
::::

::: source-block
**Paper**

[LongMemEval: five long-term memory capabilities](https://arxiv.org/abs/2410.10813){.paper}

[The multi-scale replay matrix and ACL/update constraints are proposed Mari evaluation requirements.]{.small}
:::

------------------------------------------------------------------------

[]{#artifacts}[Proposed]{.proposed-label}

## Unified artifact model

A generic envelope would give facts, answers, decisions, summaries, procedures, and graph statements common identity, scope, provenance, review, temporal, and supersession semantics.

### How it works

The payload type `T` holds domain content; the envelope holds governance. Artifact identity stays stable while each revision is immutable. Evidence and `derived_from` capture inputs, `generated_by` captures the producing activity/configuration, validity bounds describe when the claim applies, and `supersedes` closes a lineage edge without erasing history. Stores reject a revision if its evidence, scope, or predecessor is invalid.

**Research basis**[W3C PROV](https://www.w3.org/TR/prov-overview/){.paper} models entities, activities, agents, derivation, revision, and responsibility. [Nanopublications](https://arxiv.org/abs/1809.06532){.paper} attach provenance and metadata to atomic assertions. These results require first-class lineage; the single generic Python envelope is a Mari design choice to validate across artifact types.

:::::{container} diagram artifact
<div>

**KnowledgeArtifact\[T\]**

</div>

<div>

identity + revisionKnowledgeScopeevidencevalid timereview stategeneratorsupersedes

</div>
:::::

::::{container} code proposed-code
::: code-header
proposed / artifacts.py

Copy
:::

    artifact = KnowledgeArtifact[PolicyFact](
        id="fact:refund-window:enterprise", revision="sha256:8f31…",
        value=PolicyFact(days=30),
        scope=KnowledgeScope(tenant="acme", space="support"),
        evidence=answer.evidence, valid_from="2026-01-01", valid_to=None,
        recorded_at=clock.now(), review_state=ReviewState.APPROVED,
        generated_by=Activity("refund-policy/v4", model="extractor@2026-08"),
        derived_from=("github:policy/refunds.md@8f31c2a",),
        supersedes=("fact:refund-window:enterprise@v2",))
::::

------------------------------------------------------------------------

[]{#stores}[Proposed]{.proposed-label}

## Storage protocols and conformance

Capability protocols would allow independent document, artifact, vector, lexical, and graph implementations.

### How it works

Protocols specify observable behavior rather than backend classes. A store implementation declares capabilities, then runs a shared conformance suite against replay, atomic revision, isolation, deletion, deterministic ordering, and point-in-time cases. Cross-store operations use an application transaction/outbox boundary; Mari does not pretend separate databases share an atomic commit. Indexes remain disposable projections that can be rebuilt from documents and artifacts.

**Research basis**[Invariant confluence](https://arxiv.org/abs/1402.2237){.paper} shows that safe coordination depends on application invariants. Mari therefore specifies atomicity, replay, isolation, time-travel, and deletion behavior independently of backend methods. The protocol split is library design, not a result asserted by the paper.

::::{container} code proposed-code
::: code-header
proposed / stores.py

Copy
:::

    class DocumentStore(Protocol):
        def commit_sync(self, plan: SyncPlan) -> None: ...
        def get_many(self, ids: Iterable[str]) -> Sequence[KnowledgeDocument]: ...

    class ArtifactStore(Protocol):
        def apply(self, mutation: ArtifactMutation) -> None: ...
        def at_time(self, id: str, when: datetime) -> KnowledgeArtifact | None: ...

    class VectorIndex(Protocol): ...
    class LexicalIndex(Protocol): ...
    class GraphIndex(Protocol): ...
::::

Conformance tests would cover replay safety, deterministic ordering, point-in-time reads, tenant isolation, atomic revisions, and delete behavior.

------------------------------------------------------------------------

[]{#pipelines}[Proposed]{.proposed-label}

## Typed knowledge pipelines

Composable stages would transform typed inputs and emit reviewable `ArtifactMutation` values: create, revise, supersede, retract, or leave unchanged.

### How it works

Each stage declares input/output types, a versioned configuration fingerprint, and whether it is pure or calls an injected service. The runner topologically orders stages, passes immutable batches, records input revisions and stage results, and stops dependent stages after failure. Outputs are mutation proposals; a final policy validates evidence, scope, and expected artifact revision before the application commits them.

**Research basis**[Pipeline provenance research](https://arxiv.org/abs/2006.12117){.paper} ties reproducibility to captured inputs, transformations, and configuration. [Data Cascades](https://doi.org/10.1145/3411764.3445518){.paper} documents how upstream data failures compound downstream. This motivates stage identities, dependency traces, and visible failures; the generic stage and mutation types are Mari\'s composition boundary.

:::{container} diagram stages
extract*→*resolve*→*link*→*review*→*index
:::

::::{container} code proposed-code
::: code-header
proposed / pipeline.py

Copy
:::

    pipeline = Pipeline[KnowledgeDocument, KnowledgeArtifact](
        extract(FactExtractor(model=model)), resolve(EntityResolver(catalog=entities)),
        link(EvidenceLinker()), review(ReviewPolicy(min_corroboration=2)),
        index(vector=vector_index, graph=graph_index))

    result = pipeline.run(changed_documents)
    artifact_store.apply(result.mutations)
    trace_store.write(result.trace)
::::

------------------------------------------------------------------------

[]{#context}[Proposed]{.proposed-label}

## Retrieval plans and context envelopes

A retrieval plan would run explicit arms, fuse ranks, enforce scope and freshness, rerank, and pack a bounded context envelope. Its trace explains inclusion and exclusion.

### How it works

Run semantic, lexical, graph, and recency arms over authorized IDs. Convert arm scores to ranks and combine them with reciprocal-rank fusion, then discard stale dependencies, rerank survivors, diversify near-duplicates, and greedily pack whole evidence excerpts under token/document limits. The envelope contains rendered context plus source revisions and per-candidate include/exclude reasons, allowing the caller to reproduce what the model saw.

**Research basis**[RAG](https://arxiv.org/abs/2005.11401){.paper} motivates explicit, updateable non-parametric memory and provenance; [RAG-Fusion](https://arxiv.org/abs/2402.03367){.paper} and [MMR](https://www.cs.cmu.edu/afs/cs/Web/People/jgc/publication/MMR_DiversityBased_Reranking_SIGIR_1998.pdf){.paper} back fusion and diversity; [Lost in the Middle](https://arxiv.org/abs/2307.03172){.paper} makes budget and evidence order evaluation requirements. `ContextEnvelope` is Mari\'s proposed carrier for those observable decisions.

::::::{container} diagram context
::: arms
semanticlexicalgraphrecent
:::

*RRF*

<div>

**authorizefreshnessrerank**

</div>

*budget*

<div>

**ContextEnvelope**[excerpts · evidence · revisions · trace]{.small}

</div>
::::::

::::{container} code proposed-code
::: code-header
proposed / context.py

Copy
:::

    plan = RetrievalPlan(arms=[Semantic(vector_index, limit=40),
        Lexical(lexical_index, limit=30), GraphExpand(graph_index, hops=2),
        RecentChanges(window="14d")], fusion=ReciprocalRankFusion(k=60),
        reranker=ExactMaxSim())

    context = assemble_context(query, plan=plan, scope=user.knowledge_scope,
        budget=ContextBudget(tokens=6000, documents=12))
    model(context.render())
    audit(context.retrieval_trace)
::::

------------------------------------------------------------------------

[]{#graph}[Proposed]{.proposed-label}

## Bi-temporal knowledge graph

Statements would track valid time (when the claim applied) and transaction time (when the system learned it), supporting historical queries and late corrections.

### How it works

An assertion is append-only and carries two intervals. A correction learned today may close an older assertion's transaction interval while preserving its historical valid interval. Query `at` filters valid time; `known_at` filters transaction time; both must contain their requested timestamp. Contradictions create explicit edges or superseding revisions instead of destructive overwrites.

**Research basis**[Zep](https://arxiv.org/abs/2501.13956){.paper} uses a temporally aware graph to maintain historical relationships for agent memory, while the [temporal knowledge-graph survey](https://arxiv.org/abs/2201.08236){.paper} catalogs representations and inference tasks for facts that change over time. Mari adds explicit valid-time and transaction-time query semantics; interval boundaries and contradiction policy require conformance tests.

:::::{container} diagram bitemporal
<div>

**valid time**Jan ───────── Aug

</div>

<div>

**transaction time**learned Sep 01 ───▶

</div>
:::::

::::{container} code proposed-code
::: code-header
proposed / graph.py

Copy
:::

    graph.assert_fact(subject="plan:enterprise", predicate="refund_window_days",
        object=30, valid_time=Interval("2026-01-01", "2026-08-31"),
        transaction_time=clock.now(), evidence=evidence)

    then = graph.query(at="2026-06-01", known_at="2026-09-01")
    now = graph.query(at=clock.now(), known_at=clock.now())
::::

------------------------------------------------------------------------

[]{#procedures}[Proposed]{.proposed-label}

## Procedural knowledge

Successful trajectories could produce versioned procedure candidates. Regression gates and human review would separate observed behavior from active behavior.

### How it works

Cluster successful traces by reviewed intent, extract a parameterized tool/action sequence with preconditions and failure exits, and retain links to the source traces. Replay the candidate on held-out cases, compare task success, tool correctness, grounding, cost, and regressions with the active version, then produce a review proposal. Only an explicit application commit can activate a version; failed attempts remain negative evidence.

**Research basis**[Voyager](https://arxiv.org/abs/2305.16291){.paper} stores compositional skills and improves them using execution feedback, errors, and self-verification. [Reflexion](https://arxiv.org/abs/2303.11366){.paper} retains verbal feedback for later trials. They motivate persistent procedural candidates; held-out regression gates and human promotion are conservative Mari policies, not conclusions of either paper.

:::{container} diagram lifecycle
trajectories*→*candidate*→*regression suite*→*review*→*active version
:::

::::{container} code proposed-code
::: code-header
proposed / procedures.py

Copy
:::

    candidate = learn_procedure(successful_runs, intent="process enterprise refund")
    report = evaluate_procedure(candidate, cases=refund_regression_suite,
        metrics=[TaskSuccess(), ToolCorrectness(), Groundedness(), Cost()])
    if report.passes_gates:
        procedures.propose(candidate, report=report)  # review still required
::::

------------------------------------------------------------------------

[]{#compiler}[Proposed]{.proposed-label}

## Evaluation and compilation

A compiler would search pipeline and retrieval configurations against knowledge-system objectives and return a reviewable, versioned configuration proposal.

### How it works

Declare tunable parameters, hard constraints, and optimization metrics. For each candidate configuration, run the same frozen training cases, cache stage results by configuration/input fingerprints, reject any candidate that violates provenance, update fidelity, or ACL constraints, and rank feasible candidates on grounded recall, cost, and latency. Validate the selected configuration once on held-out cases; compilation returns a report and proposal, never a deployment side effect.

**Research basis**[DSPy](https://arxiv.org/abs/2310.03714){.paper} compiles parameterized LM pipelines against a declared metric. Mari generalizes the search space to retrieval, indexing, parsing, graph, consolidation, and packing configuration. Hard provenance, update-fidelity, and ACL constraints are Mari requirements and must be evaluated independently.

::::::::: metric-grid
<div>

**Grounded recall**maximize

</div>

<div>

**Provenance accuracy**require 1.0

</div>

<div>

**Update fidelity**require 1.0

</div>

<div>

**ACL leakage**require 0.0

</div>

<div>

**Context tokens**minimize

</div>

<div>

**Latency p95**minimize

</div>
:::::::::

::::{container} code proposed-code
::: code-header
proposed / compile.py

Copy
:::

    compiled = compile_knowledge_system(pipeline, trainset=train_cases,
        validation=validation_cases,  # optimizer may inspect these; never test_cases
        objectives={GroundedRecall(): Maximize(), ProvenanceAccuracy(): Require(1.0),
            UpdateFidelity(): Require(1.0), ACLLeakage(): Require(0.0),
            ContextTokens(): Minimize(), LatencyP95(): Minimize()},
        search_space=KnowledgeConfigSpace())

    review(compiled.config, compiled.report, compiled.failures)
    test_report = evaluate_once(compiled.config, cases=test_cases)
    deploy(compiled.config, evidence=test_report)  # explicit application action
::::

------------------------------------------------------------------------

`mari-kit` · Apache-2.0 · Python 3.11--3.13 · [Back to top](https://kit.mari.guru/#overview)
