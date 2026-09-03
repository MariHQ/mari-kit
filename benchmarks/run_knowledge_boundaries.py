#!/usr/bin/env python3
"""Record known-answer checks for five knowledge boundary primitives."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mari_components.knowledge import (
    DerivationInput,
    DerivationIssueKind,
    KnowledgeDerivation,
    KnowledgeEdit,
    KnowledgeObservation,
    KnowledgeObservationStage,
    KnowledgeOrigin,
    inspect_knowledge_derivations,
    inspect_knowledge_observations,
    validate_knowledge_changeset,
)
from mari_components.knowledge.artifacts import ArtifactRef
from mari_components.retrieval import (
    DisclosureCondition,
    DisclosureLevel,
    DisclosureOperator,
    DisclosureRule,
    DisclosureUnit,
    ProgressiveDisclosureManifest,
    evaluate_disclosure,
    expand_disclosure,
)
from mari_components.types import KnowledgeDocument


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/results/knowledge-boundaries.json"),
    )
    args = parser.parse_args()
    cases: list[dict[str, object]] = []

    ledger = inspect_knowledge_observations(
        [
            KnowledgeObservation(
                observation_id="retrieve",
                activity_id="a",
                artifact_id="policy",
                revision="r1",
                stage=KnowledgeObservationStage.RETRIEVED,
                ordinal=0,
            ),
            KnowledgeObservation(
                observation_id="cite",
                activity_id="a",
                artifact_id="policy",
                revision="r1",
                stage=KnowledgeObservationStage.CITED,
                ordinal=1,
            ),
        ]
    )
    cases.append(
        {
            "case_id": "observation-no-inferred-use",
            "expected": {"cited": 1, "used": 0},
            "observed": {"cited": len(ledger.cited), "used": len(ledger.used)},
            "passed": len(ledger.cited) == 1 and not ledger.used,
        }
    )

    source = KnowledgeDerivation(
        output=ArtifactRef(artifact_id="source", revision="r1"),
        origin=KnowledgeOrigin.SOURCE,
    )
    summary = KnowledgeDerivation(
        output=ArtifactRef(artifact_id="summary", revision="r1"),
        origin=KnowledgeOrigin.DERIVED,
        inputs=(DerivationInput(ref=source.output),),
    )
    recycled = KnowledgeDerivation(
        output=ArtifactRef(artifact_id="fact", revision="r1"),
        origin=KnowledgeOrigin.DERIVED,
        inputs=(DerivationInput(ref=summary.output, claimed_independent=True),),
    )
    derivation = inspect_knowledge_derivations([source, summary, recycled])
    detected = DerivationIssueKind.DERIVED_AS_INDEPENDENT in {
        issue.kind for issue in derivation.issues
    }
    cases.append(
        {
            "case_id": "derived-evidence-not-independent",
            "expected": True,
            "observed": detected,
            "passed": detected,
        }
    )

    rule = DisclosureRule(
        rule_id="incident",
        conditions=(
            DisclosureCondition(
                field="kind",
                operator=DisclosureOperator.EQUALS,
                value="incident",
            ),
        ),
    )
    observed_decisions = (
        evaluate_disclosure(rule, {"kind": "incident"}).eligible,
        evaluate_disclosure(rule, {"kind": "support"}).eligible,
    )
    cases.append(
        {
            "case_id": "conditional-disclosure",
            "expected": [True, False],
            "observed": list(observed_decisions),
            "passed": observed_decisions == (True, False),
        }
    )

    document = KnowledgeDocument(
        source_id="docs",
        external_id="policy",
        title="Policy",
        body="Limit 10. Route basic.",
        revision="r1",
    )
    changeset = validate_knowledge_changeset(
        {document.document_id: document},
        [
            KnowledgeEdit(
                document_id=document.document_id,
                source_revision="r1",
                original="10",
                replacement="20",
                reason="correct limit",
            ),
            KnowledgeEdit(
                document_id=document.document_id,
                source_revision="r1",
                original="basic",
                replacement="enterprise",
                reason="align route",
            ),
        ],
    )
    preview = changeset.entries[0].preview
    cases.append(
        {
            "case_id": "multi-edit-preview",
            "expected": "Limit 20. Route enterprise.",
            "observed": preview,
            "passed": changeset.valid and preview == "Limit 20. Route enterprise.",
        }
    )

    manifest = ProgressiveDisclosureManifest(
        root_ids=("index",),
        units=(
            DisclosureUnit(
                unit_id="index",
                artifact_id="policy",
                revision="r1",
                level=DisclosureLevel.INDEX,
                text="limits",
                token_count=2,
                expands_to=("summary",),
            ),
            DisclosureUnit(
                unit_id="summary",
                artifact_id="policy",
                revision="r1",
                level=DisclosureLevel.SUMMARY,
                text="limits by plan",
                token_count=5,
                expands_to=("source",),
            ),
            DisclosureUnit(
                unit_id="source",
                artifact_id="policy",
                revision="r1",
                level=DisclosureLevel.SOURCE,
                text="full source text",
                token_count=10,
            ),
        ),
    )
    selection = expand_disclosure(manifest, token_budget=7)
    selected_ids = [unit.unit_id for unit in selection.selected]
    cases.append(
        {
            "case_id": "progressive-budget",
            "expected": ["index", "summary"],
            "observed": selected_ids,
            "passed": selected_ids == ["index", "summary"],
        }
    )

    report = {
        "evaluation_type": "known-answer semantic conformance",
        "cases": len(cases),
        "passed": sum(bool(case["passed"]) for case in cases),
        "limitations": "Validates deterministic semantics, not application quality.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    cases_path = args.output.with_suffix(".cases.jsonl")
    cases_path.write_text(
        "".join(json.dumps(case, sort_keys=True) + "\n" for case in cases)
    )


if __name__ == "__main__":
    main()
