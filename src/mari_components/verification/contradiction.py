"""Document-level self-contradiction validation and reward components."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from numbers import Integral

_REFERENCE = re.compile(r"\[(\d+)(?:-(\d+))?\](?:-\[(\d+)\])?")


def _sentence_ids(values: Iterable[int], *, name: str) -> tuple[int, ...]:
    rows = tuple(values)
    if any(isinstance(value, bool) or not isinstance(value, Integral) for value in rows):
        raise ValueError(f"{name} must contain integer sentence IDs")
    return tuple(sorted(set(int(value) for value in rows)))


def reasoning_sentence_references(
    reasoning: str, *, sentence_count: int
) -> tuple[int, ...]:
    """Expand ``[i]``, ``[i-j]``, and ``[i]-[j]`` reasoning references.

    Sentence numbers are one-based, matching the tagged-document convention in
    reinforced reference coverage.

    Source: Chen et al., EMNLP 2025, Equation 7.
    """
    if sentence_count < 1:
        raise ValueError("sentence_count must be positive")
    covered: set[int] = set()
    for match in _REFERENCE.finditer(str(reasoning)):
        start = int(match.group(1))
        compact_end = match.group(2)
        separated_end = match.group(3)
        end = int(compact_end or separated_end or start)
        if start < 1 or end < start or end > sentence_count:
            raise ValueError("reasoning reference is outside the document")
        covered.update(range(start, end + 1))
    return tuple(sorted(covered))


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentContradictionAssessment:
    """Validated document-level judgment with localized evidence."""

    judgment: bool
    evidence_sentence_ids: tuple[int, ...]
    reasoning_sentence_ids: tuple[int, ...]
    sentence_count: int

    @property
    def reference_coverage(self) -> float:
        return len(self.reasoning_sentence_ids) / self.sentence_count


def validate_document_contradiction(
    *,
    sentence_count: int,
    judgment: bool,
    evidence_sentence_ids: Iterable[int] = (),
    reasoning: str = "",
) -> DocumentContradictionAssessment:
    """Validate a model-proposed document self-contradiction judgment.

    Positive judgments require localized evidence. Negative judgments cannot
    carry contradictory evidence. Mari validates the model output; it does not
    make the semantic judgment itself.
    """
    if sentence_count < 1:
        raise ValueError("sentence_count must be positive")
    evidence = _sentence_ids(evidence_sentence_ids, name="evidence")
    if any(value < 1 or value > sentence_count for value in evidence):
        raise ValueError("evidence sentence ID is outside the document")
    if judgment and not evidence:
        raise ValueError("a positive contradiction judgment requires evidence")
    if not judgment and evidence:
        raise ValueError("a negative contradiction judgment cannot include evidence")
    references = reasoning_sentence_references(
        reasoning, sentence_count=sentence_count
    )
    return DocumentContradictionAssessment(
        judgment=bool(judgment),
        evidence_sentence_ids=evidence,
        reasoning_sentence_ids=references,
        sentence_count=sentence_count,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentContradictionRewards:
    """The three independent RRC-DSCD reinforcement reward components."""

    accuracy: float
    reference_coverage: float
    format: float
    matched_evidence_count: int
    gold_evidence_count: int


def document_contradiction_rewards(
    assessment: DocumentContradictionAssessment,
    *,
    expected_judgment: bool,
    gold_evidence_sentence_ids: Iterable[int] = (),
    format_valid: bool,
) -> DocumentContradictionRewards:
    """Compute accuracy, reference-coverage, and format rewards.

    For a positive gold example, an incorrect judgment receives zero, a correct
    judgment without an evidence hit receives -1, and a correct judgment with
    evidence receives ``1 + matched / gold``. For a negative gold example,
    accuracy is the binary judgment reward. Components remain separate because
    the paper supplies them independently to GRPO.

    Source: Chen et al., "Think Wider, Detect Sharper" (EMNLP 2025),
    Equations 5-8.
    """
    gold = _sentence_ids(gold_evidence_sentence_ids, name="gold evidence")
    if any(value < 1 or value > assessment.sentence_count for value in gold):
        raise ValueError("gold evidence sentence ID is outside the document")
    if expected_judgment and not gold:
        raise ValueError("positive gold examples require evidence sentences")
    if not expected_judgment and gold:
        raise ValueError("negative gold examples cannot include contradiction evidence")
    judgment_correct = assessment.judgment is bool(expected_judgment)
    matched = len(set(assessment.evidence_sentence_ids).intersection(gold))
    if expected_judgment:
        if not judgment_correct:
            accuracy = 0.0
        elif matched == 0:
            accuracy = -1.0
        else:
            accuracy = 1.0 + matched / len(gold)
    else:
        accuracy = float(judgment_correct)
    return DocumentContradictionRewards(
        accuracy=accuracy,
        reference_coverage=assessment.reference_coverage,
        format=float(bool(format_valid)),
        matched_evidence_count=matched,
        gold_evidence_count=len(gold),
    )
