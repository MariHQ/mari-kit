"""Bounded behavioral tests for the company-brain scale benchmark.

These tests validate deterministic synthetic inputs, measurement helpers, and
counts from a tiny durable end-to-end run. They never assert latency
thresholds. The durable integration tests are gated until the sibling store
module lands; run them once it exists.
"""

from __future__ import annotations

import json

import pytest

from benchmarks.company_brain_scale import (
    BENCHMARK_SCHEMA,
    build_deletions,
    build_documents,
    build_edits,
    build_queries,
    engine_available,
    host_allowed_refs,
    latency_summary,
    main,
    percentile,
    process_rss_bytes,
    run,
    run_size,
)
from mari_kit import ScopeRef


def test_documents_are_deterministic_and_unique() -> None:
    first = build_documents(60, seed=7)
    second = build_documents(60, seed=7)

    assert [document.document_id for document in first] == [
        document.document_id for document in second
    ]
    assert [document.body for document in first] == [
        document.body for document in second
    ]
    assert len({document.document_id for document in first}) == 60


def test_document_corpus_is_prefix_stable_across_sizes() -> None:
    small = build_documents(25, seed=7)
    large = build_documents(100, seed=7)

    assert [document.document_id for document in small] == [
        document.document_id for document in large[:25]
    ]
    assert [document.body for document in small] == [
        document.body for document in large[:25]
    ]


def test_documents_vary_length_acl_and_sources() -> None:
    documents = build_documents(120, seed=7)
    lengths = [len(document.body.split()) for document in documents]

    assert min(lengths) < 60
    assert max(lengths) > 120
    assert {"public", "connector_scope", "restricted"} <= {
        document.acl.visibility for document in documents
    }
    assert any(document.acl.principals for document in documents)
    assert {document.source_id for document in documents}
    assert len({document.source_id for document in documents}) > 1


def test_queries_are_deterministic_and_nonempty() -> None:
    first = build_queries(15, seed=7)
    second = build_queries(15, seed=7)

    assert first == second
    assert len(first) == 15
    assert all(query.strip() for query in first)


def test_edits_replace_revision_and_body_without_duplicates() -> None:
    documents = build_documents(40, seed=7)
    edits = build_edits(documents, count=5, seed=7)
    originals = {document.document_id: document for document in documents}

    assert len(edits) == 5
    assert len({edit.document_id for edit in edits}) == 5
    for edit in edits:
        base = originals[edit.document_id]
        assert edit.revision != base.revision
        assert edit.body != base.body
        assert edit.content_digest != base.content_digest


def test_deletions_target_existing_documents() -> None:
    documents = build_documents(40, seed=7)
    deletions = build_deletions(documents, count=4)
    available = {(document.source_id, document.external_id) for document in documents}

    assert len(deletions) == 4
    assert all(
        (tombstone.source_id, tombstone.external_id) in available
        for tombstone in deletions
    )


def test_percentile_and_latency_summary_report_units() -> None:
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.0
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.95) == 4.0

    summary = latency_summary([0.01, 0.02, 0.03])

    assert summary["unit"] == "seconds"
    assert summary["count"] == 3
    assert summary["p50_seconds"] == 0.02
    assert summary["p95_seconds"] == 0.03
    assert summary["total_seconds"] == pytest.approx(0.06)


def test_percentile_rejects_empty_and_out_of_range() -> None:
    with pytest.raises(ValueError):
        percentile([], 0.5)
    with pytest.raises(ValueError):
        percentile([1.0], 1.5)


def test_process_rss_is_positive_bytes() -> None:
    value = process_rss_bytes()

    assert isinstance(value, int)
    assert value > 0


def test_host_allowed_refs_applies_open_and_group_policy() -> None:
    documents = build_documents(80, seed=7)
    scope = ScopeRef(tenant="scale", space="company")

    allowed = host_allowed_refs(
        documents, groups={"support"}, user_id="u1", scope=scope
    )

    assert 0 < len(allowed) <= len(documents)
    for document in documents:
        ref = document.ref_in(scope)
        if document.acl.visibility in {"public", "connector_scope"}:
            assert ref in allowed
        elif document.acl.visibility == "restricted":
            principals = {
                (principal.kind, principal.identifier)
                for principal in document.acl.principals
            }
            if ("team", "support") not in principals and (
                "user",
                "u1",
            ) not in principals:
                assert ref not in allowed


def test_run_requires_durable_store_or_fails_clearly(monkeypatch) -> None:
    from benchmarks import company_brain_scale

    monkeypatch.setattr(company_brain_scale, "durable_available", lambda: False)
    with pytest.raises(RuntimeError):
        run([10])


def test_engine_availability_is_boolean() -> None:
    assert isinstance(engine_available(), bool)


def test_run_size_reports_counts_and_metrics(tmp_path) -> None:
    size = 30
    result = run_size(
        size,
        seed=7,
        query_count=4,
        limit=3,
        edit_fraction=0.2,
        delete_fraction=0.1,
        tracemalloc_enabled=False,
        engine_probe=False,
        workdir=tmp_path,
    )

    counts = result["counts"]
    assert result["documents"] == size
    assert result["size"] == size
    assert result["queries"] == 4
    assert counts["commit_documents"] == size
    assert counts["live_documents"] == size
    assert counts["projection_documents"] == size
    assert counts["commit_plans"] == len(
        {d.source_id for d in build_documents(size, seed=7)}
    )
    assert counts["edit_documents"] == 6
    assert counts["delete_documents"] == 3
    assert counts["final_live_documents"] == size - 3
    assert counts["cold_index_units"] == size
    assert 0 < counts["authorized_refs"] <= counts["total_refs"]
    assert "consistency_warning" not in result
    assert result["database_bytes"] > 0

    for phase in (
        "commit",
        "cold_index_build",
        "reference_index_query",
        "acl_filtered_query",
        "batch_edit_commit",
        "batch_edit_index_update",
        "batch_delete_commit",
        "batch_delete_index_update",
    ):
        payload = result["phases"][phase]
        assert payload["wall_seconds"] >= 0.0
        assert payload["allocations_peak_bytes"] >= 0
        assert payload["process_rss_before_bytes"] > 0
        assert payload["latency"]["count"] >= 1
        assert payload["latency"]["unit"] == "seconds"

    assert result["phases"]["reference_index_query"]["latency"]["count"] == 4
    assert result["phases"]["acl_filtered_query"]["latency"]["count"] == 4
    assert result["final_projection_documents"] == size - 3


def test_cli_writes_json_report(tmp_path, capsys) -> None:
    output = tmp_path / "scale-report.json"
    exit_code = main(
        [
            "--sizes",
            "20",
            "--queries",
            "3",
            "--no-tracemalloc",
            "--no-engine",
            "--output",
            str(output),
        ]
    )
    capsys.readouterr()

    assert exit_code == 0
    report = json.loads(output.read_text())
    assert report["schema"] == BENCHMARK_SCHEMA
    assert report["sizes_requested"] == [20]
    assert len(report["results"]) == 1
    assert report["results"][0]["counts"]["live_documents"] == 20
    assert "reference_index_query" in report["results"][0]["phases"]
