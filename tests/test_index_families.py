from mari_components import KnowledgeIndex, ObjectRef, RevisionRef, ScopeRef
from mari_components.retrieval import (
    BM25Index,
    DenseFlatIndex,
    HNSWIndex,
    IVFPQIndex,
    RevisionBM25Index,
    SparseVectorIndex,
)
from mari_components.testing import assert_index_authorization_conforms


def test_dense_flat_metrics_and_acl_filtering() -> None:
    index = DenseFlatIndex({"a": [1, 0], "b": [0, 1]}, metric="cosine")
    assert [hit.document_id for hit in index.search([1, 0], limit=2)] == ["a", "b"]
    assert [
        hit.document_id
        for hit in index.search([1, 0], limit=2, allowed_document_ids={"b"})
    ] == ["b"]


def test_bm25_ranks_exact_terms() -> None:
    index = BM25Index(
        {"policy": "enterprise refund window", "other": "account settings"}
    )
    assert index.search("refund", limit=1)[0].document_id == "policy"


def test_sparse_index_accepts_model_produced_weights() -> None:
    index = SparseVectorIndex({"a": {"refund": 2, "policy": 1}, "b": {"account": 3}})
    assert index.search({"refund": 1}, limit=1)[0].document_id == "a"


def test_hnsw_matches_obvious_neighbor_and_filters_before_return() -> None:
    index = HNSWIndex({"a": [1, 0], "b": [0.9, 0.1], "c": [0, 1]}, m=2)
    assert index.search([1, 0], limit=1, ef_search=3)[0].document_id == "a"
    assert (
        index.search([1, 0], limit=1, ef_search=3, allowed_document_ids={"c"})[
            0
        ].document_id
        == "c"
    )


def test_ivfpq_trains_residual_codes_and_finds_obvious_neighbor() -> None:
    index = IVFPQIndex(
        {"a": [0, 0, 0, 0], "b": [1, 1, 1, 1], "c": [10, 10, 10, 10]},
        partitions=2,
        subquantizers=2,
        codebook_size=2,
    )
    assert index.search([0, 0, 0, 0], limit=1, probes=2)[0].document_id == "a"


def test_revision_index_uses_structural_refs_and_authorizes_before_scoring() -> None:
    scope = ScopeRef(tenant="acme", space="handbook")
    policy = RevisionRef(
        object=ObjectRef(namespace="document", object_id="policy", scope=scope),
        revision="2",
    )
    payroll = RevisionRef(
        object=ObjectRef(namespace="document", object_id="payroll", scope=scope),
        revision="4",
    )
    index = RevisionBM25Index(
        {policy: "enterprise refund window", payroll: "payroll schedule"}
    )
    assert isinstance(index, KnowledgeIndex)
    hits = index.search("refund", limit=5, allowed_refs={policy})
    assert tuple(hit.ref for hit in hits) == (policy,)
    assert index.explain("refund", ref=policy).contributions[0].term == "refund"
    assert_index_authorization_conforms(
        index,
        query="refund",
        allowed_ref=policy,
        hit_ref=lambda hit: hit.ref,
    )
