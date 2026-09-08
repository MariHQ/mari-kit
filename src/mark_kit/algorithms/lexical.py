"""BM25 family with reference-compatible term formulas and explicit matching.

Formula reference: rank_bm25 (Apache-2.0). The existing BM25Index remains an
independent positive-IDF choice. No scores are assumed calibrated across variants.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum


class BM25Variant(StrEnum):
    OKAPI = "okapi"
    L = "l"
    PLUS = "plus"


@dataclass(frozen=True, slots=True)
class LexicalTerm:
    term: str
    frequency: int
    idf: float
    score: float


@dataclass(frozen=True, slots=True)
class LexicalScore:
    item_id: str
    score: float
    matched: bool
    terms: tuple[LexicalTerm, ...]


class BM25VariantIndex:
    """Caller-tokenized immutable corpus; L/Plus retain nonmatch baselines.

    Empty corpus is allowed. An all-empty corpus has zero scores. Delta defaults
    to .5 for L and 1 for Plus. Okapi replaces negative IDFs by epsilon times
    the average raw vocabulary IDF, including when that average is negative.
    """

    def __init__(
        self,
        documents: Mapping[str, Iterable[str]],
        *,
        variant: BM25Variant,
        k1: float = 1.5,
        b: float = 0.75,
        delta: float | None = None,
        epsilon: float = 0.25,
    ):
        if not isinstance(variant, BM25Variant):
            raise ValueError("select a BM25Variant")
        delta = (0.5 if variant is BM25Variant.L else 1.0) if delta is None else delta
        if (
            not all(math.isfinite(x) for x in (k1, b, delta, epsilon))
            or k1 <= 0
            or not 0 <= b <= 1
            or min(delta, epsilon) < 0
        ):
            raise ValueError("invalid BM25 parameters")
        self.variant, self.k1, self.b, self.delta = variant, k1, b, delta
        self._docs = {key: tuple(tokens) for key, tokens in documents.items()}
        if any(
            not key or any(not isinstance(t, str) or not t for t in tokens)
            for key, tokens in self._docs.items()
        ):
            raise ValueError("nonempty IDs and string tokens required")
        self._counts = {key: Counter(tokens) for key, tokens in self._docs.items()}
        self._average = (
            sum(map(len, self._docs.values())) / len(self._docs) if self._docs else 0.0
        )
        df: Counter[str] = Counter()
        for tokens in self._docs.values():
            df.update(set(tokens))
        n = len(self._docs)
        if variant is BM25Variant.OKAPI:
            idfs = {
                term: math.log(n - freq + 0.5) - math.log(freq + 0.5)
                for term, freq in df.items()
            }
            floor = epsilon * sum(idfs.values()) / len(idfs) if idfs else 0.0
            self._idf = {
                term: floor if value < 0 else value for term, value in idfs.items()
            }
        elif variant is BM25Variant.L:
            self._idf = {
                term: math.log(n + 1) - math.log(freq + 0.5)
                for term, freq in df.items()
            }
        else:
            self._idf = {
                term: math.log(n + 1) - math.log(freq) for term, freq in df.items()
            }

    def explain(self, query: Iterable[str], item_id: str) -> LexicalScore:
        counts = self._counts[item_id]
        norm = (
            1 - self.b + self.b * len(self._docs[item_id]) / self._average
            if self._average
            else 1.0
        )
        terms = []
        for term in query:
            freq, idf = counts[term], self._idf.get(term, 0.0)
            if self.variant is BM25Variant.L:
                ctd = freq / norm if norm else 0.0
                score = (
                    idf
                    * (self.k1 + 1)
                    * (ctd + self.delta)
                    / (self.k1 + ctd + self.delta)
                )
            else:
                denominator = freq + self.k1 * norm
                saturation = freq * (self.k1 + 1) / denominator if denominator else 0.0
                score = idf * (
                    saturation
                    + (self.delta if self.variant is BM25Variant.PLUS else 0.0)
                )
            terms.append(LexicalTerm(term, freq, idf, score))
        return LexicalScore(
            item_id,
            sum(t.score for t in terms),
            any(t.frequency for t in terms),
            tuple(terms),
        )

    def search(
        self,
        query: Iterable[str],
        *,
        limit: int | None = None,
        matching_only: bool = False,
        allowed_ids: Iterable[str] | None = None,
    ) -> tuple[LexicalScore, ...]:
        if limit is not None and limit < 0:
            raise ValueError("limit must be nonnegative")
        tokens = tuple(query)
        allowed = set(self._docs) if allowed_ids is None else set(allowed_ids)
        rows = [self.explain(tokens, key) for key in self._docs if key in allowed]
        rows = [row for row in rows if not matching_only or row.matched]
        rows.sort(key=lambda row: (-row.score, row.item_id))
        return tuple(rows if limit is None else rows[:limit])
