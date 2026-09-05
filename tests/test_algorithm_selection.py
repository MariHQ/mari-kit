import itertools
import math

import numpy as np
import pytest

from mari_components.algorithms.lexical import BM25Variant, BM25VariantIndex
from mari_components.algorithms.subsets import (
    FacilityLocation,
    GreedyMethod,
    LogDeterminant,
    ProbabilisticSetCover,
    SetCover,
    maximize_subset,
)


@pytest.mark.parametrize("variant", list(BM25Variant))
def test_lexical_reference_formula(variant):
    docs = {"a": ["common", "rare", "rare"], "b": ["common"], "c": ["other"]}
    index = BM25VariantIndex(docs, variant=variant)
    n, df, tf, norm = 3, 1, 2, 0.25 + 0.75 * 3 / (5 / 3)
    if variant == BM25Variant.OKAPI:
        idf = math.log((n - df + 0.5) / (df + 0.5))
        expected = idf * tf * 2.5 / (tf + 1.5 * norm)
    elif variant == BM25Variant.L:
        idf = math.log((n + 1) / (df + 0.5))
        expected = idf * 2.5 * (tf / norm + 0.5) / (1.5 + tf / norm + 0.5)
    else:
        idf = math.log((n + 1) / df)
        expected = idf * (1 + tf * 2.5 / (tf + 1.5 * norm))
    assert index.explain(["rare"], "a").score == pytest.approx(expected)
    assert index.explain(["rare", "rare"], "a").score == pytest.approx(2 * expected)
    assert not index.explain(["rare"], "b").matched
    assert [r.item_id for r in index.search(["rare"], matching_only=True)] == ["a"]
    assert index.search(["rare"], allowed_ids={"b"})[0].item_id == "b"
    assert BM25VariantIndex({}, variant=variant).search(["a"]) == ()


def test_objective_equations_and_validation():
    assert FacilityLocation([[1, 0.5], [0.2, 0.8]]).evaluate([0, 1]) == 1.8
    assert (
        FacilityLocation(
            [[1, 0.5], [0.2, 0.8]], query_similarities=[[0.4], [0.3]]
        ).evaluate([0, 1])
        == 0.7
    )
    assert (
        ProbabilisticSetCover([[0.5, 0], [0.5, 1]], weights=[2, 3]).evaluate([0, 1])
        == 4.5
    )
    assert SetCover([[1, 0], [1, 1]], weights=[2, 3]).evaluate([0, 1]) == 5
    assert LogDeterminant([[2, 0], [0, 3]]).evaluate([0, 1]) == pytest.approx(
        math.log(12)
    )
    assert LogDeterminant(np.zeros((0, 0))).evaluate([]) == 0
    with pytest.raises(ValueError):
        LogDeterminant([[1, 2], [2, 1]])
    with pytest.raises(ValueError):
        FacilityLocation([[1]]).evaluate([0, 0])


@pytest.mark.parametrize("method", list(GreedyMethod))
def test_greedy_cardinality_cost_and_reproducibility(method):
    objective = SetCover([[1, 0, 1], [0, 1, 0], [1, 0, 0]])
    kwargs = dict(
        n=3,
        objective=objective.evaluate,
        budget=2,
        method=method,
        assume_submodular=True,
        seed=19,
    )
    result = maximize_subset(**kwargs)
    assert result.selected == (0, 1)
    assert result.value == 3
    assert result == maximize_subset(**kwargs)
    result = maximize_subset(**{**kwargs, "costs": {0: 3, 1: 1, 2: 1}})
    assert set(result.selected) == {1, 2}
    assert sum(step.cost for step in result.steps) <= 2


def test_lazy_agrees_with_naive_for_random_coverage():
    rng = np.random.default_rng(52)
    for _ in range(20):
        objective = ProbabilisticSetCover(rng.random((12, 8)))
        naive = maximize_subset(12, objective.evaluate, budget=5)
        lazy = maximize_subset(
            12,
            objective.evaluate,
            budget=5,
            method=GreedyMethod.LAZY,
            assume_submodular=True,
        )
        assert lazy.selected == naive.selected
        assert lazy.evaluations <= naive.evaluations
    with pytest.raises(ValueError):
        maximize_subset(1, lambda _: 1, budget=1, method=GreedyMethod.LAZY)


def test_marginal_diminishing_returns():
    objective = FacilityLocation([[1, 0.2, 0.7], [0.1, 1, 0.5]])
    for a, b in itertools.permutations(range(3), 2):
        assert objective.marginal_gain([], b) >= objective.marginal_gain([a], b) - 1e-12


def test_okapi_negative_average_floor_and_empty_length_normalization():
    index = BM25VariantIndex({"a": ["x"], "b": ["x"]}, variant=BM25Variant.OKAPI)
    assert index.explain(["x"], "a").score == pytest.approx(0.25 * math.log(0.5 / 2.5))
    for variant in BM25Variant:
        empty = BM25VariantIndex({"a": [], "b": ["x"]}, variant=variant, b=1)
        assert math.isfinite(empty.explain(["x"], "a").score)
