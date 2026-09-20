"""Wave-6 interleaved-workload tests for the company-brain view cache.

The wave-3/4/5 view cache is keyed by ``(scope, user, token)`` and bounded by an
LRU count and an estimated retained-byte budget, so *who* is asked *when*
changes how often an authorized view has to be rebuilt.  This benchmark feeds
one identical ``(user, query)`` multiset to a fresh
:class:`~examples.company_brains.durable.engine.CompanyBrain` in three orders
and counts the real ``access_token_snapshot`` rebuilds.

These tests pin the contract that matters for the report:

* the three orderings are exact permutations of one request multiset with full
  request counts -- the comparison is only about interleaving;
* the counting store's ``access_token_snapshot`` reads are the misses, hits are
  ``requests - misses``, and consecutive grouping never rebuilds a view inside
  one user's block while capacity-bound round-robin thrashes;
* the count bound and retained-byte budget hold under normal, tiny-budget, and
  zero-count settings;
* the report is deterministic apart from wall-clock samples;
* empty and invalid arguments are rejected by both the function and the CLI.

The tests use a deliberately small corpus so the full suite stays fast; the
benchmark's own defaults are 240 documents, 16 users, and 4 queries per user.
"""

from __future__ import annotations

import json

import pytest

from benchmarks.company_brain_cache_memory import build_users
from benchmarks.company_brain_interleaved import (
    BENCHMARK_SCHEMA,
    deterministic_signature,
    main,
    request_orderings,
    run,
)

SEED = 20240919
USERS = 6
QUERIES_PER_USER = 2
SMALL: dict[str, object] = {
    "documents": 40,
    "users": USERS,
    "queries_per_user": QUERIES_PER_USER,
    "limit": 5,
    "view_cache_size": 3,
    "view_cache_bytes": 1_000_000,
    "seed": SEED,
}


# --------------------------------------------------------------------------- #
# Orderings
# --------------------------------------------------------------------------- #


def test_orderings_are_full_multiset_permutations() -> None:
    user_specs = build_users(USERS, seed=SEED)
    orderings = request_orderings(
        user_specs, queries_per_user=QUERIES_PER_USER, seed=SEED
    )

    reference = sorted(orderings["consecutive"])
    assert len(reference) == USERS * QUERIES_PER_USER
    assert set(orderings) == {"consecutive", "round_robin", "hot_interleaved"}
    for requests in orderings.values():
        assert len(requests) == USERS * QUERIES_PER_USER
        assert sorted(requests) == reference


def test_orderings_differ_only_in_user_adjacency() -> None:
    user_specs = build_users(USERS, seed=SEED)
    orderings = request_orderings(
        user_specs, queries_per_user=QUERIES_PER_USER, seed=SEED
    )

    def switches(requests) -> int:  # type: ignore[no-untyped-def]
        return sum(
            1
            for previous, current in zip(requests, requests[1:], strict=False)
            if previous[0] != current[0]
        )

    # Consecutive grouping has exactly one switch between each pair of users.
    assert switches(orderings["consecutive"]) == USERS - 1
    # Round-robin switches on nearly every request.
    total = USERS * QUERIES_PER_USER
    assert switches(orderings["round_robin"]) == total - 1
    # The hot user's own requests are spread, not adjacent.
    hot = user_specs[0][0]
    hot_positions = [
        index
        for index, (user_id, _query) in enumerate(orderings["hot_interleaved"])
        if user_id == hot
    ]
    assert len(hot_positions) == QUERIES_PER_USER
    assert all(
        later - earlier > 1
        for earlier, later in zip(hot_positions, hot_positions[1:], strict=False)
    )


def test_orderings_reject_empty_and_unknown_hot_user() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        request_orderings([], queries_per_user=2, seed=SEED)
    with pytest.raises(ValueError, match="hot_user"):
        request_orderings(
            build_users(USERS, seed=SEED),
            queries_per_user=QUERIES_PER_USER,
            seed=SEED,
            hot_user="nobody",
        )
    with pytest.raises(ValueError, match="queries_per_user"):
        request_orderings(
            build_users(USERS, seed=SEED),
            queries_per_user=0,
            seed=SEED,
        )


# --------------------------------------------------------------------------- #
# Reporting contract
# --------------------------------------------------------------------------- #


def test_report_has_full_counts_and_equal_multisets() -> None:
    report = run(**SMALL)  # type: ignore[arg-type]

    assert report["schema"] == BENCHMARK_SCHEMA
    expected = USERS * QUERIES_PER_USER
    configuration = report["configuration"]
    assert configuration["requests_per_strategy"] == expected
    assert configuration["users"] == USERS
    assert configuration["queries_per_user"] == QUERIES_PER_USER

    workload = report["workload"]
    assert workload["request_multiset_size"] == expected
    assert workload["request_multiset_equal"] is True
    fingerprints = {row["fingerprint"] for row in workload["orderings"].values()}
    assert len(fingerprints) == 1
    assert workload["request_multiset_fingerprint"] in fingerprints

    assert [row["name"] for row in report["strategies"]] == [
        "consecutive",
        "round_robin",
        "hot_interleaved",
    ]
    for strategy in report["strategies"]:
        assert strategy["requests"] == expected
        assert strategy["view_misses"] + strategy["view_hits"] == expected
        assert 0 <= strategy["view_misses"] <= expected
        assert 0 <= strategy["view_hits"] <= expected
        assert strategy["hit_rate"] == pytest.approx(
            strategy["view_hits"] / expected, abs=1e-6
        )
        assert strategy["latency"]["count"] == expected
        assert len(strategy["latency_samples_seconds"]) == expected


def test_bounds_hold_and_cache_stats_are_consistent() -> None:
    report = run(**SMALL)  # type: ignore[arg-type]

    for strategy in report["strategies"]:
        stats = strategy["cache_stats"]
        assert strategy["within_count_bound"] is True
        assert strategy["within_byte_budget"] is True
        assert strategy["within_bounds"] is True
        assert stats["views"] <= SMALL["view_cache_size"]
        assert stats["retained_estimated_bytes"] <= SMALL["view_cache_bytes"]
        assert stats["max_views"] == SMALL["view_cache_size"]
        assert stats["max_bytes"] == SMALL["view_cache_bytes"]
        assert stats["evictions"] >= 0
        assert stats["evicted_estimated_bytes"] >= 0


def test_consecutive_grouping_rides_the_cache_while_round_robin_thrashes() -> None:
    report = run(**SMALL)  # type: ignore[arg-type]
    by_name = {row["name"]: row for row in report["strategies"]}
    consecutive = by_name["consecutive"]
    round_robin = by_name["round_robin"]
    hot = by_name["hot_interleaved"]
    expected = USERS * QUERIES_PER_USER

    # Back-to-back queries rebuild each user's view exactly once: the user's
    # block is contiguous, so nothing can evict it between their own questions.
    assert consecutive["view_misses"] == USERS

    # The LRU count is smaller than the user population, so cycling one query
    # per user evicts every view before its next turn: every request misses.
    assert SMALL["view_cache_size"] < USERS
    assert round_robin["view_misses"] == expected
    assert round_robin["view_hits"] == 0

    # Spreading the hot user through cold traffic cannot beat grouping.
    assert hot["view_misses"] >= consecutive["view_misses"]
    assert consecutive["view_hits"] > round_robin["view_hits"]


def test_tiny_byte_budget_evicts_everything_but_still_holds() -> None:
    report = run(**{**SMALL, "view_cache_bytes": 1})  # type: ignore[arg-type]
    for strategy in report["strategies"]:
        stats = strategy["cache_stats"]
        assert strategy["within_byte_budget"] is True
        assert strategy["within_bounds"] is True
        assert stats["retained_estimated_bytes"] <= 1
        assert stats["views"] == 0


def test_zero_count_bound_evicts_everything_but_still_holds() -> None:
    report = run(**{**SMALL, "view_cache_size": 0})  # type: ignore[arg-type]
    for strategy in report["strategies"]:
        stats = strategy["cache_stats"]
        assert strategy["within_count_bound"] is True
        assert strategy["within_bounds"] is True
        assert stats["views"] == 0
        assert stats["max_views"] == 0


def test_byte_budget_can_be_disabled() -> None:
    report = run(
        **{**SMALL, "view_cache_bytes": None}  # type: ignore[arg-type]
    )
    assert report["configuration"]["view_cache_bytes"] is None
    for strategy in report["strategies"]:
        assert strategy["cache_stats"]["max_bytes"] is None
        assert strategy["within_byte_budget"] is True


def test_report_is_deterministic_apart_from_wall_samples() -> None:
    first = run(**SMALL)  # type: ignore[arg-type]
    second = run(**SMALL)  # type: ignore[arg-type]
    assert deterministic_signature(first) == deterministic_signature(second)


# --------------------------------------------------------------------------- #
# Invalid arguments and CLI
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("override", "match"),
    [
        ({"documents": 0}, "documents"),
        ({"documents": True}, "documents"),
        ({"documents": -1}, "documents"),
        ({"users": 0}, "users"),
        ({"queries_per_user": 0}, "queries_per_user"),
        ({"limit": 0}, "limit"),
        ({"view_cache_size": -1}, "view_cache_size"),
        ({"view_cache_size": True}, "view_cache_size"),
        ({"view_cache_bytes": -1}, "view_cache_bytes"),
        ({"hot_user": "nobody"}, "hot_user"),
    ],
)
def test_run_rejects_invalid_arguments(override: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        run(**{**SMALL, **override})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "argv",
    [
        ["--documents", "0"],
        ["--users", "0"],
        ["--queries-per-user", "0"],
        ["--limit", "0"],
        ["--count", "-1"],
        ["--budget", "-1"],
    ],
)
def test_cli_rejects_invalid_arguments(argv: list[str]) -> None:
    with pytest.raises(SystemExit):
        main(argv)


def test_cli_writes_a_configured_report(tmp_path) -> None:
    output = tmp_path / "report.json"
    code = main(
        [
            "--documents",
            "30",
            "--users",
            "4",
            "--queries-per-user",
            "2",
            "--limit",
            "3",
            "--count",
            "2",
            "--budget",
            "500000",
            "--seed",
            "7",
            "--output",
            str(output),
        ]
    )
    assert code == 0
    report = json.loads(output.read_text())
    configuration = report["configuration"]
    assert configuration["documents"] == 30
    assert configuration["users"] == 4
    assert configuration["queries_per_user"] == 2
    assert configuration["limit"] == 3
    assert configuration["view_cache_size"] == 2
    assert configuration["view_cache_bytes"] == 500000
    assert report["seed"] == 7
    assert report["workload"]["request_multiset_equal"] is True
    assert all(row["within_bounds"] for row in report["strategies"])


def test_cli_no_byte_budget_disables_the_budget(tmp_path) -> None:
    output = tmp_path / "report.json"
    assert (
        main(
            [
                "--documents",
                "30",
                "--users",
                "4",
                "--queries-per-user",
                "2",
                "--no-byte-budget",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    report = json.loads(output.read_text())
    assert report["configuration"]["view_cache_bytes"] is None
    assert all(row["within_byte_budget"] for row in report["strategies"])
