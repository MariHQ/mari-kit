import io
import math
from datetime import UTC, datetime

import pytest

from mari_components.algorithms.compression import (
    TextSpan,
    fastcdc_chunks,
    select_surprising_words,
)
from mari_components.algorithms.linkage import (
    BlockingPredicate,
    PairScore,
    acquire_disagreement,
    centroid_clusters,
    gazette_matching,
    greedy_matching,
    learn_blocking,
)
from mari_components.algorithms.memory import (
    MemoryNote,
    NoteUpdate,
    SkillDecision,
    SkillFeedback,
    SkillRecord,
    evolve_neighborhood,
    heat_promotions,
    lfu_evictions,
    memory_heat,
    reduce_skill_feedback,
)
from mari_components.algorithms.search import (
    DriftQuery,
    DriftResponse,
    drift_search,
    refine_extraction,
)
from mari_components.algorithms.temporal import (
    dated_recency,
    recency_decay,
    temporal_proof_score,
)


@pytest.mark.parametrize(
    ("method", "days", "expected"),
    [
        ("none", 100, 0.5),
        ("linear", 1000, 0.1),
        ("linear", -3, 1),
        ("exponential", 90, 0.5),
        ("exponential", -1e300, 1),
    ],
)
def test_recency(method, days, expected):
    assert recency_decay(days, method=method) == expected


def test_coarse_dates_and_score_factors():
    now = datetime(2026, 8, 1, tzinfo=UTC)
    assert (
        dated_recency(now=now, start=datetime(2026, 1, 1), end=datetime(2027, 1, 1))
        == 0.5
    )
    assert dated_recency(now=now, start=now) == 1
    assert dated_recency(now=now) == 0.5
    assert temporal_proof_score(0.8) == 0.8
    assert temporal_proof_score(
        0.8, recency=1, proximity=1, proof_count=1000
    ) == pytest.approx(0.8 * 1.1 * 1.1 * 1.05)
    with pytest.raises(ValueError):
        recency_decay(2, half_life=0)


def test_surprisal_alignment_and_original_spans():
    text = "hello rare common"
    words = [TextSpan(0, 5), TextSpan(6, 10), TextSpan(11, 17)]
    result = select_surprising_words(
        text, words, words, [0.8, 0.001, 0.9], fraction=0.5
    )
    assert result.text == "rare"
    assert result.spans == (words[1],)
    assert result.scores == (pytest.approx(-math.log2(0.001)),)
    with pytest.raises(ValueError):
        select_surprising_words(text, words, words[:2], [0.8, 0.001], fraction=1)


@pytest.mark.parametrize("length", [0, 1, 63, 64, 65, 1024, 10000])
def test_fastcdc_stream_invariants(length):
    data = bytes((i * i + i * 17) % 256 for i in range(length))

    class ShortReader(io.BytesIO):
        def read(self, size=-1):
            return super().read(min(size, 7))

    chunks = tuple(
        fastcdc_chunks(io.BytesIO(data), minimum=64, average=256, maximum=1024)
    )
    assert chunks == tuple(
        fastcdc_chunks(ShortReader(data), minimum=64, average=256, maximum=1024)
    )
    assert b"".join(c.data for c in chunks) == data
    assert all(64 <= len(c.data) <= 1024 for c in chunks[:-1])
    assert [c.offset for c in chunks] == [
        sum(len(p.data) for p in chunks[:i]) for i in range(len(chunks))
    ]


def test_drift_ranking_cycles_depth_budget_and_reduction():
    def local(query, depth):
        return DriftResponse(
            query.query, (DriftQuery("high", 4), DriftQuery("child", 2))
        )

    result = drift_search(
        "question",
        primer=lambda _: [DriftQuery("low", 1), DriftQuery("high", 3)],
        local_search=local,
        reduce=lambda _, actions: tuple(a.response.answer for a in actions),
        max_actions=2,
        max_depth=1,
    )
    assert result.answer == ("high", "child")
    assert result.stopped == "budget"
    assert len(result.actions) == 3
    assert result.actions[2].parent == 1
    exhausted = drift_search(
        "q",
        primer=lambda _: [DriftQuery("high")],
        local_search=local,
        reduce=lambda _, actions: len(actions),
        max_depth=0,
    )
    assert exhausted.answer == 1 and exhausted.stopped == "exhausted"


def test_refinement_merges_and_stops():
    result = refine_extraction(
        "source",
        extract=lambda _: [("a", "short")],
        refine=lambda _, records, round_: [("a", "long description"), ("b", "new")],
        key=lambda r: r[0],
        merge=lambda a, b: max((a, b), key=lambda r: len(r[1])),
        max_rounds=4,
    )
    assert result.records == (("a", "long description"), ("b", "new"))
    assert result.rounds == 2 and result.stopped == "stable"
    with pytest.raises(ValueError):
        refine_extraction(
            "",
            extract=lambda _: [("a", "")],
            refine=lambda *_: [("a", "")],
            key=lambda r: r[0],
            merge=lambda *_: ("changed", ""),
        )


def test_heat_and_lfu_choices():
    assert memory_heat(2, 3, 24) == pytest.approx(5 + math.exp(-1))
    assert lfu_evictions({"a": 2, "b": 1, "c": 1}, capacity=1) == ("b", "c")
    assert heat_promotions({"a": 3, "b": 5, "c": 4}, threshold=3, limit=1) == ("b",)
    with pytest.raises(ValueError):
        lfu_evictions({"a": 1}, capacity=0, protected=frozenset({"a"}))


def test_neighborhood_plan_revision_and_scope():
    a, b = MemoryNote("a", 2, "a"), MemoryNote("b", 4, "b")
    changes = evolve_neighborhood(
        a,
        [b],
        propose=lambda *_: [
            NoteUpdate("a", 2, add_links=("b",)),
            NoteUpdate("b", 4, context="updated"),
        ],
    )
    assert changes[0].after.revision == 3
    assert changes[1].after.context == "updated"
    assert a.links == () and b.context == "b"
    for update in [NoteUpdate("b", 3), NoteUpdate("a", 2, add_links=("secret",))]:
        with pytest.raises(ValueError):
            evolve_neighborhood(a, [b], propose=lambda *_, update=update: [update])


def test_skill_feedback_replay_and_merge_provenance():
    records = [
        SkillRecord("a", "first", helpful=2, provenance=("one",)),
        SkillRecord("b", "second", harmful=1),
    ]
    feedback = [SkillFeedback("event", "b", "helpful", "two")]
    result = reduce_skill_feedback(
        records, feedback, decisions=[SkillDecision("merge", "a", ("b",), "combined")]
    )
    assert result.records[0].helpful == 3
    assert result.records[0].harmful == 1
    assert result.records[0].provenance == ("one", "two")
    assert result.records[1].deleted
    assert (
        reduce_skill_feedback(
            result.records, feedback, applied_events=result.applied_events
        )
        == result
    )
    assert records[1].helpful == 0


def test_blocking_optimization_limits_and_infeasibility():
    predicates = [
        BlockingPredicate("all", frozenset({"1", "2"}), 10),
        BlockingPredicate("one", frozenset({"1"}), 2),
        BlockingPredicate("two", frozenset({"2"}), 3),
    ]
    result = learn_blocking(predicates, frozenset({"1", "2"}))
    assert result.predicates == ("one", "two") and result.cost == 5 and result.optimal
    assert not learn_blocking(predicates, frozenset({"1", "2", "3"})).feasible
    assert not learn_blocking(predicates, frozenset({"1", "2"}), max_states=1).optimal
    assert acquire_disagreement({"a": 0.9, "b": 0.1}, {"a": False, "b": True}) == "a"
    assert acquire_disagreement({"a": 0.0}, {"a": False}) == "a"


def test_matching_choices_and_centroid_confidence():
    pairs = [
        PairScore("a", "x", 0.9),
        PairScore("a", "y", 0.8),
        PairScore("b", "x", 0.85),
    ]
    assert greedy_matching(pairs) == (pairs[0],)
    assert gazette_matching(pairs) == (pairs[0], pairs[2])
    assert len(gazette_matching(pairs, n_matches=0)) == 3
    pytest.importorskip("scipy")
    clusters = centroid_clusters(
        [PairScore("a", "b", 0.9), PairScore("a", "c", 0.9), PairScore("b", "c", 0.9)],
        threshold=0.8,
    )
    assert clusters[0].members == ("a", "b", "c")
    assert clusters[0].confidence == pytest.approx((0.9, 0.9, 0.9))
    assert centroid_clusters([PairScore("a", "b", 0.5)]) == ()
