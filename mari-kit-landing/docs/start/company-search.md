[]{#company-search}[Supported composition]{.current-label}

# Build company search

## Flow

This composition stores canonical source revisions, builds a replaceable index,
applies an authorization result during candidate scoring, and returns the exact
revision used as context.

```{literalinclude} ../../../examples/quickstarts/company_search.py
:language: python
:caption: An authorized revision-bound search path
```

`InMemoryDocumentStore` supplies reference semantics. A production adapter can
implement `DocumentStore` and run `assert_document_store_conforms` against its
transaction and isolation behavior. `BM25Index` can be replaced by a dense,
multi-vector, graph, or external index. The document and authorization
boundaries stay unchanged.

The application computes `allowed_ids` from its own identity and policy system.
The index receives that set before it scores candidates.

| Decision | Default in this example | Other Mari tools |
|---|---|---|
| Canonical storage | In-memory reference store | Application `DocumentStore` adapter |
| Candidate generation | BM25 | Dense flat, sparse vector, HNSW, IVF-PQ, MUVERA |
| Authorization | Explicit allowed-ID set | Application `Authorizer` implementation |
| Returned context | Whole document body | Semantic atoms and neighbor expansion |
