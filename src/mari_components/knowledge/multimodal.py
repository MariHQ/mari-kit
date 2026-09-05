"""Revision-bound asset selection; byte loading and message rendering stay external.

Adapted from haiku.rag's picture retention rules; see THIRD_PARTY_NOTICES.md.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from mari_components.references import LocatedEvidence, RevisionRef


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceAsset:
    """One source asset, with source captions separate from generated descriptions.

    ``ref`` names the asset within its source revision. It is not a storage URL.
    """

    ref: RevisionRef
    media_type: str
    captions: tuple[str, ...] = ()
    description: str = ""
    description_model: str = ""

    def __post_init__(self) -> None:
        if not self.ref.unit_id or "/" not in self.media_type:
            raise ValueError("assets require a unit reference and media type")
        object.__setattr__(self, "captions", tuple(self.captions))


@dataclass(frozen=True, slots=True, kw_only=True)
class AssetBinding:
    """An asset associated with a specific retained evidence unit."""

    evidence: RevisionRef
    asset: EvidenceAsset

    def __post_init__(self) -> None:
        if (
            self.evidence.object != self.asset.ref.object
            or self.evidence.revision != self.asset.ref.revision
        ):
            raise ValueError(
                "asset and evidence must belong to the same source revision"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class RetainedAsset:
    asset: EvidenceAsset
    evidence_refs: tuple[RevisionRef, ...]
    origin: str = "retrieved_evidence"


@dataclass(frozen=True, slots=True, kw_only=True)
class AssetSelection:
    assets: tuple[RetainedAsset, ...]
    excluded_refs: tuple[RevisionRef, ...]


def select_evidence_assets(
    bindings: Iterable[AssetBinding],
    *,
    retained_evidence: Iterable[LocatedEvidence],
    allowed_asset_refs: Iterable[RevisionRef],
    already_attached: Iterable[RevisionRef] = (),
) -> AssetSelection:
    """Deduplicate by full revision identity, only for surviving evidence.

    The host supplies currently authorized asset revisions. No bytes are read,
    MIME type inferred, or user attachments inspected. Conflicting descriptions
    of one asset are rejected instead of depending on input order.
    """
    retained = {item.ref for item in retained_evidence}
    allowed = set(allowed_asset_refs)
    attached = set(already_attached)
    assets: dict[RevisionRef, EvidenceAsset] = {}
    sources: dict[RevisionRef, list[RevisionRef]] = {}
    excluded: set[RevisionRef] = set()
    for binding in bindings:
        ref = binding.asset.ref
        if binding.evidence not in retained or ref not in allowed or ref in attached:
            excluded.add(ref)
            continue
        if ref in assets and assets[ref] != binding.asset:
            raise ValueError("conflicting metadata for one asset revision")
        assets[ref] = binding.asset
        owners = sources.setdefault(ref, [])
        if binding.evidence not in owners:
            owners.append(binding.evidence)
    return AssetSelection(
        assets=tuple(
            RetainedAsset(asset=asset, evidence_refs=tuple(sources[ref]))
            for ref, asset in assets.items()
        ),
        excluded_refs=tuple(sorted(excluded - assets.keys(), key=lambda ref: ref.key)),
    )
