"""Small deterministic pipeline runner with visible stage failures."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from mari_components.json import canonical_json_bytes, freeze_json_mapping


@dataclass(frozen=True, slots=True, kw_only=True)
class Stage:
    name: str
    version: str
    transform: Callable[[tuple[Any, ...]], Iterable[Any]]
    configuration: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.version.strip():
            raise ValueError("stage name and version are required")
        object.__setattr__(
            self, "configuration", freeze_json_mapping(self.configuration)
        )

    @property
    def fingerprint(self) -> str:
        encoded = canonical_json_bytes(
            {
                "name": self.name,
                "version": self.version,
                "configuration": self.configuration,
            }
        )
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True, kw_only=True)
class StageTrace:
    name: str
    fingerprint: str
    input_count: int
    output_count: int
    succeeded: bool
    error: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class PipelineResult:
    outputs: tuple[Any, ...]
    trace: tuple[StageTrace, ...]

    @property
    def succeeded(self) -> bool:
        return all(stage.succeeded for stage in self.trace)


@dataclass(frozen=True, slots=True, kw_only=True)
class Pipeline:
    stages: tuple[Stage, ...]

    def __post_init__(self) -> None:
        if not self.stages:
            raise ValueError("pipeline requires at least one stage")
        names = [stage.name for stage in self.stages]
        if len(names) != len(set(names)):
            raise ValueError("pipeline stage names must be unique")

    def run(self, inputs: Iterable[Any]) -> PipelineResult:
        values = tuple(inputs)
        trace: list[StageTrace] = []
        for stage in self.stages:
            try:
                output = tuple(stage.transform(values))
            except Exception as error:  # boundaries convert host errors into data
                trace.append(
                    StageTrace(
                        name=stage.name,
                        fingerprint=stage.fingerprint,
                        input_count=len(values),
                        output_count=0,
                        succeeded=False,
                        error=f"{type(error).__name__}: {error}",
                    )
                )
                return PipelineResult(outputs=(), trace=tuple(trace))
            trace.append(
                StageTrace(
                    name=stage.name,
                    fingerprint=stage.fingerprint,
                    input_count=len(values),
                    output_count=len(output),
                    succeeded=True,
                )
            )
            values = output
        return PipelineResult(outputs=values, trace=tuple(trace))
