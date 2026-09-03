"""Turn trajectory evidence and expert feedback into reviewable knowledge changes."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from mari_components.errors import MalformedModelOutput
from mari_components.json import require_list
from mari_components.types import KnowledgeDocument

if TYPE_CHECKING:
    from mari_components.trajectories.process import TrajectoryRun

EXPERIENCE_KNOWLEDGE_VERSION = "experience-knowledge-v1"


@dataclass(frozen=True, slots=True, kw_only=True)
class TrajectoryEvidence:
    trajectory_id: str
    start: int
    end: int


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeUse:
    artifact_id: str
    revision: str
    first_step: int
    last_step: int
    use: str


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeUseManifest:
    trajectory_id: str
    uses: tuple[KnowledgeUse, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ExpertFeedback:
    feedback_id: str
    correction: str
    evidence: TrajectoryEvidence


class FeedbackRootCause(StrEnum):
    KNOWLEDGE_GAP = "knowledge_gap"
    PROCEDURE_GAP = "procedure_gap"
    AMBIGUITY = "ambiguity"
    TOOL_EXECUTION = "tool_execution"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True, kw_only=True)
class FeedbackDiagnosis:
    feedback_id: str
    root_cause: FeedbackRootCause
    could_resolve_from_loaded_knowledge: bool | None
    supporting_artifact_ids: tuple[str, ...]
    evidence: tuple[TrajectoryEvidence, ...]
    explanation: str


class ExperienceKnowledgeKind(StrEnum):
    FACT = "fact"
    STRATEGY = "strategy"
    PITFALL = "pitfall"
    CONSTRAINT = "constraint"


@dataclass(frozen=True, slots=True, kw_only=True)
class ExperienceKnowledgeCandidate:
    candidate_id: str
    kind: ExperienceKnowledgeKind
    title: str
    content: str
    evidence: tuple[TrajectoryEvidence, ...]
    applicability: tuple[str, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeFile:
    artifact_id: str
    revision: str
    token_count: int
    depends_on: tuple[str, ...] = ()
    referenced_by: tuple[str, ...] = ()


class KnowledgeStructureIssueKind(StrEnum):
    DUPLICATE_ID = "duplicate_id"
    MISSING_REFERENCE = "missing_reference"
    ASYMMETRIC_REFERENCE = "asymmetric_reference"
    DEPENDENCY_CYCLE = "dependency_cycle"
    TOKEN_BUDGET = "token_budget"


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeStructureIssue:
    kind: KnowledgeStructureIssueKind
    artifact_id: str
    related_id: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeStructureReport:
    issues: tuple[KnowledgeStructureIssue, ...]
    total_tokens: int

    @property
    def valid(self) -> bool:
        return not self.issues


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeEdit:
    document_id: str
    source_revision: str
    original: str
    replacement: str
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeChangeProposal:
    proposal_id: str
    diagnosis_ids: tuple[str, ...]
    edits: tuple[KnowledgeEdit, ...]
    affected_artifact_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ChangeEvaluation:
    targeted_before: float
    targeted_after: float
    regression_before: float
    regression_after: float
    blind_review_scores: tuple[float, ...]

    @property
    def targeted_delta(self) -> float:
        return self.targeted_after - self.targeted_before

    @property
    def regression_delta(self) -> float:
        return self.regression_after - self.regression_before


def build_knowledge_use_manifest(
    run: TrajectoryRun, uses: Iterable[KnowledgeUse]
) -> KnowledgeUseManifest:
    """Validate which immutable knowledge revisions were available at which steps."""

    values = tuple(uses)
    for item in values:
        if (
            not item.artifact_id.strip()
            or not item.revision.strip()
            or not item.use.strip()
            or item.first_step < 0
            or item.last_step < item.first_step
            or item.last_step >= len(run.steps)
        ):
            raise ValueError(
                "knowledge use must identify an in-range artifact revision"
            )
    return KnowledgeUseManifest(
        trajectory_id=run.trajectory_id,
        uses=tuple(
            sorted(
                set(values),
                key=lambda item: (
                    item.first_step,
                    item.last_step,
                    item.artifact_id,
                    item.revision,
                ),
            )
        ),
    )


def parse_feedback_diagnoses(
    runs: Iterable[TrajectoryRun],
    manifests: Iterable[KnowledgeUseManifest],
    feedback: Iterable[ExpertFeedback],
    model_output: object,
) -> tuple[FeedbackDiagnosis, ...]:
    """Validate root-cause proposals against feedback, runs, and loaded knowledge."""

    run_by_id = {run.trajectory_id: run for run in runs}
    manifest_by_id = {item.trajectory_id: item for item in manifests}
    feedback_by_id = {item.feedback_id: item for item in feedback}
    for item in feedback_by_id.values():
        run = run_by_id.get(item.evidence.trajectory_id)
        if (
            run is None
            or item.evidence.start < 0
            or item.evidence.end >= len(run.steps)
        ):
            raise ValueError("feedback evidence is outside the known trajectories")
    rows = require_list(model_output, "diagnoses", recipe=EXPERIENCE_KNOWLEDGE_VERSION)
    output: list[FeedbackDiagnosis] = []
    seen: set[str] = set()
    for row in rows:
        feedback_id = str(row.get("feedback_id") or "")
        if feedback_id not in feedback_by_id or feedback_id in seen:
            raise MalformedModelOutput("diagnosis feedback is unknown or repeated")
        try:
            cause = FeedbackRootCause(str(row.get("root_cause") or "unknown"))
        except ValueError as error:
            raise MalformedModelOutput("feedback root cause is invalid") from error
        resolvable = row.get("could_resolve_from_loaded_knowledge")
        if resolvable is not None and not isinstance(resolvable, bool):
            raise MalformedModelOutput(
                "knowledge resolvability must be boolean or null"
            )
        if cause is FeedbackRootCause.KNOWLEDGE_GAP and resolvable is not False:
            raise MalformedModelOutput(
                "knowledge gaps require a negative resolvability finding"
            )
        if cause is FeedbackRootCause.PROCEDURE_GAP and resolvable is not True:
            raise MalformedModelOutput(
                "procedure gaps require a positive resolvability finding"
            )
        raw_artifacts = row.get("supporting_artifact_ids", [])
        if not isinstance(raw_artifacts, list):
            raise MalformedModelOutput("supporting artifact IDs must be a list")
        artifact_ids = tuple(dict.fromkeys(str(item) for item in raw_artifacts))
        trajectory_id = feedback_by_id[feedback_id].evidence.trajectory_id
        loaded = {
            item.artifact_id
            for item in manifest_by_id.get(
                trajectory_id,
                KnowledgeUseManifest(trajectory_id=trajectory_id, uses=()),
            ).uses
        }
        if set(artifact_ids) - loaded:
            raise MalformedModelOutput(
                "diagnosis cites knowledge not loaded in the trajectory"
            )
        explanation = str(row.get("explanation") or "").strip()[:1_000]
        if not explanation:
            raise MalformedModelOutput("feedback diagnosis explanation is required")
        output.append(
            FeedbackDiagnosis(
                feedback_id=feedback_id,
                root_cause=cause,
                could_resolve_from_loaded_knowledge=resolvable,
                supporting_artifact_ids=artifact_ids,
                evidence=(feedback_by_id[feedback_id].evidence,),
                explanation=explanation,
            )
        )
        seen.add(feedback_id)
    return tuple(output)


def parse_experience_knowledge(
    runs: Iterable[TrajectoryRun], model_output: object
) -> tuple[ExperienceKnowledgeCandidate, ...]:
    """Validate facts, strategies, pitfalls, and constraints extracted from runs."""

    known = {run.trajectory_id: run for run in runs}
    rows = require_list(model_output, "knowledge", recipe=EXPERIENCE_KNOWLEDGE_VERSION)
    output: list[ExperienceKnowledgeCandidate] = []
    for row in rows:
        title = str(row.get("title") or "").strip()[:160]
        content = str(row.get("content") or "").strip()[:2_000]
        if not title or not content:
            raise MalformedModelOutput(
                "experience knowledge title and content are required"
            )
        try:
            kind = ExperienceKnowledgeKind(str(row.get("kind") or "fact"))
        except ValueError as error:
            raise MalformedModelOutput(
                "experience knowledge kind is invalid"
            ) from error
        evidence = _trajectory_evidence(row.get("evidence"), known)
        applicability = _strings(row.get("applicability", []), "applicability")
        limitations = _strings(row.get("limitations", []), "limitations")
        identity = "\0".join(
            (
                kind.value,
                title.casefold(),
                content,
                *(f"{item.trajectory_id}:{item.start}:{item.end}" for item in evidence),
            )
        )
        output.append(
            ExperienceKnowledgeCandidate(
                candidate_id=f"experience:{hashlib.sha256(identity.encode()).hexdigest()[:20]}",
                kind=kind,
                title=title,
                content=content,
                evidence=evidence,
                applicability=applicability,
                limitations=limitations,
            )
        )
    by_id = {item.candidate_id: item for item in output}
    return tuple(by_id[key] for key in sorted(by_id))


def inspect_knowledge_structure(
    files: Iterable[KnowledgeFile], *, maximum_tokens: int | None = None
) -> KnowledgeStructureReport:
    """Check dependency symmetry, reachability, cycles, identity, and token budget."""

    values = tuple(files)
    issues: list[KnowledgeStructureIssue] = []
    counts: dict[str, int] = {}
    for item in values:
        counts[item.artifact_id] = counts.get(item.artifact_id, 0) + 1
        if item.token_count < 0:
            raise ValueError("knowledge token counts must not be negative")
    by_id = {item.artifact_id: item for item in values}
    for artifact_id, count in counts.items():
        if count > 1:
            issues.append(
                KnowledgeStructureIssue(
                    kind=KnowledgeStructureIssueKind.DUPLICATE_ID,
                    artifact_id=artifact_id,
                )
            )
    for item in values:
        for dependency in item.depends_on:
            if dependency not in by_id:
                issues.append(
                    KnowledgeStructureIssue(
                        kind=KnowledgeStructureIssueKind.MISSING_REFERENCE,
                        artifact_id=item.artifact_id,
                        related_id=dependency,
                    )
                )
            elif item.artifact_id not in by_id[dependency].referenced_by:
                issues.append(
                    KnowledgeStructureIssue(
                        kind=KnowledgeStructureIssueKind.ASYMMETRIC_REFERENCE,
                        artifact_id=item.artifact_id,
                        related_id=dependency,
                    )
                )
        for consumer in item.referenced_by:
            if consumer not in by_id:
                issues.append(
                    KnowledgeStructureIssue(
                        kind=KnowledgeStructureIssueKind.MISSING_REFERENCE,
                        artifact_id=item.artifact_id,
                        related_id=consumer,
                    )
                )
            elif item.artifact_id not in by_id[consumer].depends_on:
                issues.append(
                    KnowledgeStructureIssue(
                        kind=KnowledgeStructureIssueKind.ASYMMETRIC_REFERENCE,
                        artifact_id=item.artifact_id,
                        related_id=consumer,
                    )
                )
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(identifier: str) -> None:
        if identifier in visiting:
            issues.append(
                KnowledgeStructureIssue(
                    kind=KnowledgeStructureIssueKind.DEPENDENCY_CYCLE,
                    artifact_id=identifier,
                )
            )
            return
        if identifier in visited:
            return
        visiting.add(identifier)
        for dependency in by_id[identifier].depends_on:
            if dependency in by_id:
                visit(dependency)
        visiting.remove(identifier)
        visited.add(identifier)

    for identifier in sorted(by_id):
        visit(identifier)
    total_tokens = sum(item.token_count for item in values)
    if maximum_tokens is not None and total_tokens > maximum_tokens:
        issues.append(
            KnowledgeStructureIssue(
                kind=KnowledgeStructureIssueKind.TOKEN_BUDGET,
                artifact_id="*",
            )
        )
    unique = {(item.kind, item.artifact_id, item.related_id): item for item in issues}
    return KnowledgeStructureReport(
        issues=tuple(
            unique[key] for key in sorted(unique, key=lambda row: tuple(map(str, row)))
        ),
        total_tokens=total_tokens,
    )


def parse_knowledge_change(
    documents: Mapping[str, KnowledgeDocument],
    diagnoses: Iterable[FeedbackDiagnosis],
    model_output: object,
) -> KnowledgeChangeProposal:
    """Validate bounded exact-substring edits without applying them."""

    diagnosis_ids = {item.feedback_id for item in diagnoses}
    value = model_output if isinstance(model_output, dict) else None
    if value is None:
        raise MalformedModelOutput("knowledge change must be an object")
    raw_diagnoses = value.get("diagnosis_ids")
    if not isinstance(raw_diagnoses, list) or not raw_diagnoses:
        raise MalformedModelOutput("knowledge change diagnosis IDs are required")
    cited = tuple(dict.fromkeys(str(item) for item in raw_diagnoses))
    if set(cited) - diagnosis_ids:
        raise MalformedModelOutput("knowledge change references an unknown diagnosis")
    rows = value.get("edits")
    if not isinstance(rows, list) or not rows:
        raise MalformedModelOutput("knowledge change edits are required")
    edits: list[KnowledgeEdit] = []
    for row in rows:
        if not isinstance(row, dict):
            raise MalformedModelOutput("knowledge edits must be objects")
        document_id = str(row.get("document_id") or "")
        document = documents.get(document_id)
        original = str(row.get("original") or "")
        replacement = str(row.get("replacement") or "")
        reason = str(row.get("reason") or "").strip()[:500]
        if document is None or not original or document.body.count(original) != 1:
            raise MalformedModelOutput(
                "edit original must occur exactly once in its document"
            )
        if not replacement or replacement == original or not reason:
            raise MalformedModelOutput("edit replacement and reason are required")
        edits.append(
            KnowledgeEdit(
                document_id=document_id,
                source_revision=document.revision,
                original=original,
                replacement=replacement,
                reason=reason,
            )
        )
    affected = value.get("affected_artifact_ids", [])
    if not isinstance(affected, list):
        raise MalformedModelOutput("affected artifact IDs must be a list")
    identity = repr((cited, edits, affected)).encode()
    return KnowledgeChangeProposal(
        proposal_id=f"knowledge-change:{hashlib.sha256(identity).hexdigest()[:20]}",
        diagnosis_ids=cited,
        edits=tuple(edits),
        affected_artifact_ids=tuple(sorted(set(map(str, affected)))),
    )


def _trajectory_evidence(
    value: object, known: Mapping[str, TrajectoryRun]
) -> tuple[TrajectoryEvidence, ...]:
    if not isinstance(value, list) or not value:
        raise MalformedModelOutput("trajectory evidence is required")
    output: list[TrajectoryEvidence] = []
    for item in value:
        if not isinstance(item, dict):
            raise MalformedModelOutput("trajectory evidence must be objects")
        trajectory_id = str(item.get("trajectory_id") or "")
        run = known.get(trajectory_id)
        if run is None:
            raise MalformedModelOutput("trajectory evidence references an unknown run")
        if isinstance(item.get("start"), bool) or isinstance(item.get("end"), bool):
            raise MalformedModelOutput("trajectory evidence bounds must be integers")
        try:
            start, end = int(item["start"]), int(item["end"])
        except (KeyError, TypeError, ValueError) as error:
            raise MalformedModelOutput(
                "trajectory evidence bounds must be integers"
            ) from error
        if start < 0 or end < start or end >= len(run.steps):
            raise MalformedModelOutput("trajectory evidence is outside the run")
        output.append(
            TrajectoryEvidence(trajectory_id=trajectory_id, start=start, end=end)
        )
    return tuple(
        sorted(set(output), key=lambda item: (item.trajectory_id, item.start, item.end))
    )


def _strings(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise MalformedModelOutput(f"experience knowledge {name} must be strings")
    return tuple(item.strip()[:500] for item in value if item.strip())
