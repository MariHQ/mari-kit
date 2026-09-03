from mari_components.graph import (
    build_community_reports,
    leiden_communities,
    map_reduce_reports,
)


def test_community_partition_is_connected_deterministic_and_acl_bounded() -> None:
    graph = {
        "a": {"b": 3.0},
        "b": {"a": 3.0, "c": 0.1},
        "c": {"b": 0.1, "d": 3.0},
        "d": {"c": 3.0},
        "secret": {"a": 99.0},
    }

    partition = leiden_communities(graph, allowed_node_ids={"a", "b", "c", "d"})

    assert partition.communities == (("a", "b"), ("c", "d"))
    assert all("secret" not in community for community in partition.communities)


def test_community_reports_keep_map_and_reduce_calls_injected() -> None:
    partition = leiden_communities({"a": {"b": 1.0}, "b": {"a": 1.0}})
    reports = build_community_reports(
        partition, summarize=lambda nodes: " + ".join(nodes)
    )

    answer = map_reduce_reports(
        reports,
        map_report=lambda report: report.text,
        reduce_answers=lambda partials: " | ".join(partials),
    )

    assert answer == "a + b"
