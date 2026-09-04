"""Reproducibility metadata for persisted evaluation outputs."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from mari_components.json import freeze_json_mapping


@dataclass(frozen=True, slots=True, kw_only=True)
class EvaluationRun:
    run_id: str
    corpus_id: str
    corpus_revision: str
    split: str
    mari_revision: str
    started_at: dt.datetime
    metrics: Mapping[str, float]
    configuration: Mapping[str, Any] = field(default_factory=dict)
    model_identifiers: tuple[str, ...] = ()
    seed: int | None = None

    def __post_init__(self) -> None:
        required = (
            self.run_id,
            self.corpus_id,
            self.corpus_revision,
            self.split,
            self.mari_revision,
        )
        if any(not value.strip() for value in required):
            raise ValueError("run and revision identities are required")
        if self.started_at.tzinfo is None or self.started_at.utcoffset() is None:
            raise ValueError("started_at must be timezone-aware")
        object.__setattr__(
            self,
            "metrics",
            MappingProxyType(
                {key: float(value) for key, value in self.metrics.items()}
            ),
        )
        object.__setattr__(
            self, "configuration", freeze_json_mapping(self.configuration)
        )
        object.__setattr__(self, "model_identifiers", tuple(self.model_identifiers))
