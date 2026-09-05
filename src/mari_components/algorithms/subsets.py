"""Set objectives and independently selectable greedy optimizers.

Equations: Submodlib; facility-location MI follows Iyer et al.'s submodular
information measures. Lazy greedy follows Minoux; stochastic greedy follows
Mirzasoleiman et al. See docs/algorithm-choices.md for exact references/limits.
"""

from __future__ import annotations

import heapq
import math
import random
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _matrix(values: ArrayLike) -> NDArray[np.float64]:
    matrix = np.array(values, dtype=np.float64, copy=True)
    if matrix.ndim != 2 or not np.all(np.isfinite(matrix)):
        raise ValueError("finite two-dimensional matrix required")
    matrix.flags.writeable = False
    return matrix


def _indices(indices: Iterable[int], n: int) -> list[int]:
    values = list(indices)
    if len(set(values)) != len(values) or any(
        not isinstance(i, int) or i < 0 or i >= n for i in values
    ):
        raise ValueError("unique in-range integer indices required")
    return values


class FacilityLocation:
    """Sum of best selected similarity per represented row; nonnegative kernel.

    A rectangular matrix supports a represented set different from candidates.
    Optional query similarities implement FL1MI by capping each represented row
    at eta * max query similarity (including an empty query set).
    """

    def __init__(
        self,
        similarities: ArrayLike,
        *,
        query_similarities: ArrayLike | None = None,
        eta: float = 1.0,
    ):
        self.matrix = _matrix(similarities)
        if np.any(self.matrix < 0) or not math.isfinite(eta) or eta < 0:
            raise ValueError("nonnegative similarities and eta required")
        self.n = self.matrix.shape[1]
        self.cap = None
        if query_similarities is not None:
            query = _matrix(query_similarities)
            if query.shape[0] != self.matrix.shape[0] or np.any(query < 0):
                raise ValueError("query rows must match represented rows")
            self.cap = eta * np.max(query, axis=1, initial=0.0)

    def evaluate(self, subset: Iterable[int]) -> float:
        ids = _indices(subset, self.n)
        best = np.max(self.matrix[:, ids], axis=1, initial=0.0)
        return float(np.sum(best if self.cap is None else np.minimum(best, self.cap)))

    def marginal_gain(self, subset: Iterable[int], item: int) -> float:
        ids = tuple(_indices(subset, self.n))
        _indices((item,), self.n)
        return 0.0 if item in ids else self.evaluate((*ids, item)) - self.evaluate(ids)


class ProbabilisticSetCover:
    """Sum_c weight[c] * (1 - product_selected(1 - p[item,c]))."""

    def __init__(
        self, probabilities: ArrayLike, *, weights: Sequence[float] | None = None
    ):
        self.matrix = _matrix(probabilities)
        if np.any(self.matrix < 0) or np.any(self.matrix > 1):
            raise ValueError("coverage probabilities must be in [0,1]")
        self.n = self.matrix.shape[0]
        self.weights = np.array(
            weights if weights is not None else np.ones(self.matrix.shape[1]),
            dtype=float,
        )
        if (
            self.weights.shape != (self.matrix.shape[1],)
            or not np.all(np.isfinite(self.weights))
            or np.any(self.weights < 0)
        ):
            raise ValueError("finite nonnegative concept weights required")
        self.weights.flags.writeable = False

    def evaluate(self, subset: Iterable[int]) -> float:
        ids = _indices(subset, self.n)
        return float(self.weights @ (1 - np.prod(1 - self.matrix[ids], axis=0)))

    def marginal_gain(self, subset: Iterable[int], item: int) -> float:
        ids = tuple(_indices(subset, self.n))
        _indices((item,), self.n)
        return 0.0 if item in ids else self.evaluate((*ids, item)) - self.evaluate(ids)


class SetCover(ProbabilisticSetCover):
    """Weighted deterministic set cover from a binary item/concept matrix."""

    def __init__(self, incidence: ArrayLike, *, weights: Sequence[float] | None = None):
        matrix = _matrix(incidence)
        if np.any((matrix != 0) & (matrix != 1)):
            raise ValueError("set cover incidence must be binary")
        super().__init__(matrix, weights=weights)


class LogDeterminant:
    """log det(K_A + regularization*I), with f(empty)=0.

    K must be symmetric positive semidefinite. This objective is submodular;
    monotonicity is not promised for arbitrary regularization/kernel scaling.
    """

    def __init__(self, kernel: ArrayLike, *, regularization: float = 1.0):
        self.matrix = _matrix(kernel)
        self.n = self.matrix.shape[0]
        if self.matrix.shape != (self.n, self.n) or not np.allclose(
            self.matrix, self.matrix.T, rtol=1e-10, atol=1e-12
        ):
            raise ValueError("symmetric square kernel required")
        if self.n and np.linalg.eigvalsh(self.matrix).min() < -1e-10:
            raise ValueError("positive semidefinite kernel required")
        if not math.isfinite(regularization) or regularization <= 0:
            raise ValueError("positive regularization required")
        self.regularization = regularization

    def evaluate(self, subset: Iterable[int]) -> float:
        ids = _indices(subset, self.n)
        sign, logdet = np.linalg.slogdet(
            self.matrix[np.ix_(ids, ids)] + self.regularization * np.eye(len(ids))
        )
        if sign <= 0:
            raise ValueError("selected kernel is not positive definite")
        return float(logdet)

    def marginal_gain(self, subset: Iterable[int], item: int) -> float:
        ids = tuple(_indices(subset, self.n))
        _indices((item,), self.n)
        return 0.0 if item in ids else self.evaluate((*ids, item)) - self.evaluate(ids)


class GreedyMethod(StrEnum):
    NAIVE = "naive"
    LAZY = "lazy"
    STOCHASTIC = "stochastic"
    LAZIER = "lazier"


@dataclass(frozen=True, slots=True)
class SelectionStep:
    item: int
    marginal_gain: float
    cost: float
    total_cost: float


@dataclass(frozen=True, slots=True)
class SubsetSelection:
    selected: tuple[int, ...]
    steps: tuple[SelectionStep, ...]
    value: float
    evaluations: int
    remaining: tuple[int, ...]
    method: GreedyMethod


def maximize_subset(
    n: int,
    objective: Callable[[tuple[int, ...]], float],
    *,
    budget: float,
    method: GreedyMethod = GreedyMethod.NAIVE,
    costs: Mapping[int, float] | None = None,
    max_items: int | None = None,
    seed: int = 0,
    epsilon: float = 0.1,
    cost_sensitive: bool = False,
    assume_submodular: bool = False,
    minimum_gain: float = 0.0,
) -> SubsetSelection:
    """Greedy variants with stable index ties and explicit evaluation counts.

    Lazy bounds require a deterministic submodular objective. Stochastic samples
    use ceil(n/k*log(1/epsilon)), where k is max_items or floor(budget/min_cost).
    The standard stochastic approximation guarantee applies to monotone
    submodular cardinality constraints, not arbitrary costs. Cost-sensitive
    greedy ranks by gain/cost and makes no general knapsack-optimality claim.
    """
    if (
        n < 0
        or not math.isfinite(budget)
        or budget < 0
        or not isinstance(method, GreedyMethod)
    ):
        raise ValueError("invalid ground set, budget, or method")
    if max_items is not None and max_items < 0:
        raise ValueError("max_items must be nonnegative")
    if not 0 < epsilon < 1 or not math.isfinite(minimum_gain):
        raise ValueError("invalid epsilon or minimum gain")
    if method in (GreedyMethod.LAZY, GreedyMethod.LAZIER) and not assume_submodular:
        raise ValueError("lazy bounds require assume_submodular=True")
    if costs is not None and set(costs) != set(range(n)):
        raise ValueError("costs must cover the ground set exactly")
    cost = {i: float(costs[i]) if costs is not None else 1.0 for i in range(n)}
    if any(not math.isfinite(c) or c <= 0 for c in cost.values()):
        raise ValueError("positive finite costs required")
    evaluations = 0

    def evaluate(ids: tuple[int, ...]) -> float:
        nonlocal evaluations
        value = float(objective(ids))
        evaluations += 1
        if not math.isfinite(value):
            raise ValueError("objective must return finite values")
        return value

    selected: tuple[int, ...] = ()
    value = evaluate(selected)
    used = 0.0
    remaining = set(range(n))
    steps: list[SelectionStep] = []
    bounds: dict[int, tuple[float, float, int]] = {}
    rng = random.Random(seed)
    k = (
        max_items
        if max_items is not None
        else min(n, int(budget / min(cost.values(), default=1.0)))
    )
    sample_size = max(1, math.ceil(n / max(1, k) * math.log(1 / epsilon)))

    def compute(i: int) -> tuple[float, float, int]:
        gain = evaluate((*selected, i)) - value
        return gain / cost[i] if cost_sensitive else gain, gain, len(selected)

    while remaining and (max_items is None or len(selected) < max_items):
        feasible = sorted(i for i in remaining if used + cost[i] <= budget)
        if not feasible:
            break
        if method in (GreedyMethod.STOCHASTIC, GreedyMethod.LAZIER):
            feasible = sorted(rng.sample(feasible, min(sample_size, len(feasible))))
        if method in (GreedyMethod.LAZY, GreedyMethod.LAZIER):
            heap = []
            for i in feasible:
                if i not in bounds:
                    bounds[i] = compute(i)
                heapq.heappush(heap, (-bounds[i][0], i))
            chosen = feasible[0]
            while heap:
                _, chosen = heapq.heappop(heap)
                if bounds[chosen][2] == len(selected):
                    break
                bounds[chosen] = compute(chosen)
                heapq.heappush(heap, (-bounds[chosen][0], chosen))
            gain = bounds[chosen][1]
        else:
            scored = [(compute(i), i) for i in feasible]
            best, chosen = min(scored, key=lambda row: (-row[0][0], row[1]))
            gain = best[1]
        if gain <= minimum_gain:
            # A sampled round may miss positive candidates. Report partial
            # selection explicitly; callers can choose a smaller epsilon.
            break
        selected = (*selected, chosen)
        value += gain
        used += cost[chosen]
        remaining.remove(chosen)
        steps.append(SelectionStep(chosen, gain, cost[chosen], used))
    return SubsetSelection(
        selected, tuple(steps), value, evaluations, tuple(sorted(remaining)), method
    )
