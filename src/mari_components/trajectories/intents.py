"""Evidence-bound intent proposals and corpus-level intent aggregation."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum

from mari_components.errors import MalformedModelOutput
from mari_components.json import require_list

from .process import TrajectoryRun

INTENT_MINING_VERSION = "trajectory-intents-v1"


class IntentKind(StrEnum):
    DECLARED = "declared"
    INFERRED = "inferred"
    HINDSIGHT = "hindsight"


def normalize_intent(intent: str) -> str:
    """Return a conservative key for cosmetic intent-label variants."""

    folded = unicodedata.normalize("NFKC", str(intent)).casefold()
    return " ".join(re.sub(r"[\W_]+", " ", folded, flags=re.UNICODE).split())


@dataclass(frozen=True, slots=True, kw_only=True)
class IntentEvidence:
    trajectory_id: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if not self.trajectory_id.strip() or self.start < 0 or self.end < self.start:
            raise ValueError(
                "intent evidence requires a trajectory and valid step range"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class IntentCandidate:
    candidate_id: str
    intent: str
    kind: IntentKind
    evidence: tuple[IntentEvidence, ...]
    actual_outcome: str = ""
    limitations: tuple[str, ...] = ()
    schema_version: str = INTENT_MINING_VERSION

    def __post_init__(self) -> None:
        if (
            not self.candidate_id
            or not normalize_intent(self.intent)
            or not self.evidence
        ):
            raise ValueError(
                "intent candidate identity, label, and evidence are required"
            )
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "limitations", tuple(self.limitations))


@dataclass(frozen=True, slots=True, kw_only=True)
class IntentAggregate:
    key: str
    labels: tuple[str, ...]
    candidate_ids: tuple[str, ...]
    trajectory_ids: tuple[str, ...]
    kinds: tuple[IntentKind, ...]

    @property
    def support(self) -> int:
        return len(self.trajectory_ids)


@dataclass(frozen=True, slots=True, kw_only=True)
class IntentReview:
    candidate_id: str
    reviewer_id: str
    valid: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class IntentReviewSummary:
    candidate_id: str
    valid_reviews: int
    invalid_reviews: int
    reviewer_ids: tuple[str, ...]
    duplicate_reviewer_ids: tuple[str, ...]

    @property
    def agreement(self) -> float:
        total = self.valid_reviews + self.invalid_reviews
        return max(self.valid_reviews, self.invalid_reviews) / total if total else 0.0


def parse_intent_candidates(
    runs: Iterable[TrajectoryRun],
    model_output: object,
) -> tuple[IntentCandidate, ...]:
    """Validate model-proposed intents against exact trajectory step ranges.

    This validates identity and localization, not whether the label is a
    semantically correct description. Use independent reviews for that signal.
    """

    allowed = {run.trajectory_id: run for run in runs}
    rows = require_list(model_output, "intents", recipe=INTENT_MINING_VERSION)
    output: list[IntentCandidate] = []
    seen: set[str] = set()
    for row in rows:
        intent = str(row.get("intent") or "").strip()
        if not normalize_intent(intent):
            raise MalformedModelOutput("trajectory intent is required")
        try:
            kind = IntentKind(str(row.get("kind") or IntentKind.INFERRED))
        except ValueError as error:
            raise MalformedModelOutput("trajectory intent kind is invalid") from error
        raw_evidence = row.get("evidence")
        if not isinstance(raw_evidence, list) or not raw_evidence:
            raise MalformedModelOutput(
                "trajectory intent evidence must be a non-empty list"
            )
        evidence: list[IntentEvidence] = []
        for item in raw_evidence:
            if not isinstance(item, dict):
                raise MalformedModelOutput("trajectory intent evidence must be objects")
            trajectory_id = str(item.get("trajectory_id") or "")
            run = allowed.get(trajectory_id)
            if run is None:
                raise MalformedModelOutput(
                    "trajectory intent references an unknown trajectory"
                )
            try:
                start, end = int(item["start"]), int(item["end"])
            except (KeyError, TypeError, ValueError) as error:
                raise MalformedModelOutput(
                    "trajectory intent bounds must be integers"
                ) from error
            if start < 0 or end < start or end >= len(run.steps):
                raise MalformedModelOutput(
                    "trajectory intent evidence is outside the trajectory"
                )
            evidence.append(
                IntentEvidence(trajectory_id=trajectory_id, start=start, end=end)
            )
        unique_evidence = tuple(
            sorted(
                set(evidence),
                key=lambda item: (item.trajectory_id, item.start, item.end),
            )
        )
        identity = "\0".join(
            (
                kind.value,
                normalize_intent(intent),
                *(
                    f"{item.trajectory_id}:{item.start}:{item.end}"
                    for item in unique_evidence
                ),
            )
        )
        candidate_id = f"intent:{hashlib.sha256(identity.encode()).hexdigest()[:20]}"
        if candidate_id in seen:
            continue
        limitations = row.get("limitations", [])
        if not isinstance(limitations, list) or any(
            not isinstance(item, str) for item in limitations
        ):
            raise MalformedModelOutput("trajectory intent limitations must be strings")
        output.append(
            IntentCandidate(
                candidate_id=candidate_id,
                intent=intent[:300],
                kind=kind,
                evidence=unique_evidence,
                actual_outcome=str(row.get("actual_outcome") or "")[:1000],
                limitations=tuple(
                    item.strip()[:300] for item in limitations if item.strip()
                ),
            )
        )
        seen.add(candidate_id)
    return tuple(output)


def aggregate_intents(
    candidates: Iterable[IntentCandidate],
    *,
    key: Callable[[str], str] = normalize_intent,
) -> tuple[IntentAggregate, ...]:
    """Group candidate labels without choosing a canonical ontology."""

    groups: dict[str, list[IntentCandidate]] = {}
    for candidate in candidates:
        group = key(candidate.intent).strip()
        if not group:
            raise ValueError("intent grouping key cannot be empty")
        groups.setdefault(group, []).append(candidate)
    return tuple(
        IntentAggregate(
            key=group,
            labels=tuple(sorted({item.intent for item in values})),
            candidate_ids=tuple(sorted(item.candidate_id for item in values)),
            trajectory_ids=tuple(
                sorted({e.trajectory_id for item in values for e in item.evidence})
            ),
            kinds=tuple(sorted({item.kind for item in values}, key=str)),
        )
        for group, values in sorted(groups.items())
    )


def summarize_intent_reviews(
    candidates: Iterable[IntentCandidate],
    reviews: Iterable[IntentReview],
) -> tuple[IntentReviewSummary, ...]:
    """Expose independent-review counts without applying an acceptance threshold."""

    candidate_ids = {candidate.candidate_id for candidate in candidates}
    grouped: dict[str, list[IntentReview]] = {key: [] for key in candidate_ids}
    for review in reviews:
        if review.candidate_id not in grouped:
            raise ValueError("intent review references an unknown candidate")
        if not review.reviewer_id.strip():
            raise ValueError("intent reviewer ID is required")
        grouped[review.candidate_id].append(review)
    output: list[IntentReviewSummary] = []
    for candidate_id, values in sorted(grouped.items()):
        by_reviewer: dict[str, IntentReview] = {}
        duplicates: set[str] = set()
        for review in values:
            if review.reviewer_id in by_reviewer:
                duplicates.add(review.reviewer_id)
                continue
            by_reviewer[review.reviewer_id] = review
        output.append(
            IntentReviewSummary(
                candidate_id=candidate_id,
                valid_reviews=sum(item.valid for item in by_reviewer.values()),
                invalid_reviews=sum(not item.valid for item in by_reviewer.values()),
                reviewer_ids=tuple(sorted(by_reviewer)),
                duplicate_reviewer_ids=tuple(sorted(duplicates)),
            )
        )
    return tuple(output)
