"""Plan conversation evidence retention without rewriting stored history.

Adapted from haiku.rag's evidence capsule; see THIRD_PARTY_NOTICES.md.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from mari_components.references import LocatedEvidence, RevisionRef

from .multimodal import AssetBinding, AssetSelection, select_evidence_assets
from .observations import KnowledgeObservation, KnowledgeObservationStage


@dataclass(frozen=True, slots=True, kw_only=True)
class CompactionEvidence:
    """Canonical evidence for an observation's artifact/revision pair.

    Observation artifact IDs must be namespaced by the caller. Multiple scoped
    objects must not share one observation identity. Costs are caller-computed
    for the intended rendering, including asset costs when applicable.
    """

    artifact_id: str
    evidence: LocatedEvidence
    token_count: int
    assets: tuple[AssetBinding, ...] = ()

    def __post_init__(self) -> None:
        if not self.artifact_id.strip() or self.token_count < 0:
            raise ValueError(
                "compaction evidence requires identity and nonnegative cost"
            )
        object.__setattr__(self, "assets", tuple(self.assets))
        if any(binding.evidence != self.evidence.ref for binding in self.assets):
            raise ValueError("asset bindings must reference their compaction evidence")

    @property
    def key(self) -> tuple[str, str]:
        return self.artifact_id, self.evidence.ref.revision


class CompactionExclusion(StrEnum):
    NOT_CITED = "not_cited"
    CURRENT_ACTIVITY = "current_activity"
    UNAVAILABLE = "unavailable"
    BUDGET = "budget"


@dataclass(frozen=True, slots=True, kw_only=True)
class CompactionTrace:
    artifact_id: str
    revision: str
    reason: CompactionExclusion | None


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceGroup:
    activity_id: str
    evidence: tuple[CompactionEvidence, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceCompactionPlan:
    groups: tuple[EvidenceGroup, ...]
    assets: AssetSelection
    compact_observation_ids: tuple[str, ...]
    protected_observation_ids: tuple[str, ...]
    token_count: int
    trace: tuple[CompactionTrace, ...]


def plan_evidence_compaction(
    observations: Iterable[KnowledgeObservation],
    evidence: Iterable[CompactionEvidence],
    *,
    activity_order: Sequence[str],
    current_activity_id: str,
    allowed_evidence_refs: Iterable[RevisionRef],
    allowed_asset_refs: Iterable[RevisionRef],
    token_budget: int | None = None,
) -> EvidenceCompactionPlan:
    """Keep whole cited units, newest citing activity first, deduplicated.

    ``activity_order`` orders completed activities followed by the current one;
    observation ordinals only order events *within* an activity. Allowed refs
    must reflect the host's current revision and authorization decisions. Omitted
    evidence is reported explicitly. Current activity payloads are protected.
    The plan neither authorizes deletion nor changes the durable transcript.
    """
    order = tuple(activity_order)
    if (
        not order
        or order[-1] != current_activity_id
        or any(not value.strip() for value in order)
        or len(set(order)) != len(order)
    ):
        raise ValueError("unique activity order must end with the current activity")
    if token_budget is not None and token_budget < 0:
        raise ValueError("token budget must be nonnegative")
    values = tuple(observations)
    if len({row.observation_id for row in values}) != len(values):
        raise ValueError("observation IDs must be unique")
    positions = {activity: index for index, activity in enumerate(order)}
    if any(row.activity_id not in positions for row in values):
        raise ValueError("observation activity is absent from activity_order")
    records: dict[tuple[str, str], CompactionEvidence] = {}
    canonical_refs: set[RevisionRef] = set()
    for record in evidence:
        if record.key in records:
            raise ValueError("duplicate or ambiguous observation evidence identity")
        if record.evidence.ref in canonical_refs:
            raise ValueError(
                "multiple observation identities refer to one canonical evidence unit"
            )
        canonical_refs.add(record.evidence.ref)
        records[record.key] = record
    cited: dict[tuple[str, str], str] = {}
    active: set[tuple[str, str]] = set()
    observed = {(row.artifact_id, row.revision) for row in values}
    for row in values:
        key = row.artifact_id, row.revision
        if row.activity_id == current_activity_id:
            active.add(key)
        elif row.stage is KnowledgeObservationStage.CITED:
            if key not in records:
                raise ValueError("cited observation has no canonical evidence record")
            prior = cited.get(key)
            if prior is None or positions[row.activity_id] > positions[prior]:
                cited[key] = row.activity_id
    allowed = set(allowed_evidence_refs)
    grouped: dict[str, list[CompactionEvidence]] = {}
    trace: list[CompactionTrace] = []
    used = 0
    for key in sorted(
        observed, key=lambda key: (-positions[cited[key]] if key in cited else 1, key)
    ):
        record = records.get(key)
        reason = (
            CompactionExclusion.CURRENT_ACTIVITY
            if key in active
            else CompactionExclusion.NOT_CITED
            if key not in cited
            else CompactionExclusion.UNAVAILABLE
            if record is None or record.evidence.ref not in allowed
            else CompactionExclusion.BUDGET
            if token_budget is not None and used + record.token_count > token_budget
            else None
        )
        if reason is None:
            assert record is not None
            grouped.setdefault(cited[key], []).append(record)
            used += record.token_count
        trace.append(
            CompactionTrace(artifact_id=key[0], revision=key[1], reason=reason)
        )
    retained = [record for group in grouped.values() for record in group]
    return EvidenceCompactionPlan(
        groups=tuple(
            EvidenceGroup(activity_id=activity, evidence=tuple(group))
            for activity, group in grouped.items()
        ),
        assets=select_evidence_assets(
            (binding for record in retained for binding in record.assets),
            retained_evidence=(record.evidence for record in retained),
            allowed_asset_refs=allowed_asset_refs,
        ),
        compact_observation_ids=tuple(
            row.observation_id
            for row in values
            if row.activity_id != current_activity_id
            and row.stage
            in (KnowledgeObservationStage.RETRIEVED, KnowledgeObservationStage.SHOWN)
        ),
        protected_observation_ids=tuple(
            row.observation_id
            for row in values
            if row.activity_id == current_activity_id
        ),
        token_count=used,
        trace=tuple(trace),
    )
