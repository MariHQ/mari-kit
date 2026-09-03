#!/usr/bin/env python3
"""Measure incremental invalidation on a real Markdown document."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

from mari_components.documents import (
    align_atoms,
    parse_markdown,
    plan_atom_refresh,
    semantic_atoms,
)


def fixed_chunks(text: str, size: int = 500) -> tuple[str, ...]:
    tokens = text.split()
    return tuple(
        hashlib.sha256(" ".join(tokens[start : start + size]).encode()).hexdigest()
        for start in range(0, len(tokens), size)
    )


def revision(path: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path.parent), "rev-parse", "HEAD"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--markdown", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/results/semantic-atoms.json"),
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("benchmarks/results/semantic-atoms.cases.jsonl"),
    )
    args = parser.parse_args()
    old_text = args.markdown.read_text()
    first_line = old_text.find("\n") + 1
    new_text = (
        old_text[:first_line]
        + "\nThis inserted benchmark paragraph tests stable incremental indexing.\n"
        + old_text[first_line:]
    )
    needle = "knowledge base"
    if needle not in new_text:
        raise ValueError("benchmark document must contain 'knowledge base'")
    new_text = new_text.replace(needle, "knowledge system", 1)

    started = time.perf_counter()
    old_document = parse_markdown(
        old_text, artifact_id="public-markdown", revision="old"
    ).values[0]
    new_document = parse_markdown(
        new_text, artifact_id="public-markdown", revision="new"
    ).values[0]
    old_atoms = semantic_atoms(old_document)
    new_atoms = semantic_atoms(new_document)
    alignment = align_atoms(old_atoms, new_atoms)
    refresh = plan_atom_refresh(alignment)
    elapsed_ms = (time.perf_counter() - started) * 1_000

    old_fixed, new_fixed = fixed_chunks(old_text), fixed_chunks(new_text)
    fixed_invalidated = sum(
        index >= len(old_fixed) or old_fixed[index] != value
        for index, value in enumerate(new_fixed)
    )
    report = {
        "evaluation_type": "public-document incremental invalidation",
        "source": {
            "name": args.markdown.name,
            "sha256": hashlib.sha256(old_text.encode()).hexdigest(),
            "repository_revision": revision(args.markdown),
        },
        "edit": {"inserted_paragraphs": 1, "modified_phrases": 1},
        "semantic_atoms": {
            "before": len(old_atoms),
            "after": len(new_atoms),
            "raw_vectors_reused": len(refresh.reuse_raw_embeddings),
            "contextual_vectors_reused": len(refresh.reuse_contextual_embeddings),
            "raw_vectors_to_embed": len(refresh.embed_raw_atom_ids),
            "contextual_vectors_to_embed": len(refresh.embed_contextual_atom_ids),
            "tombstoned": len(refresh.tombstone_atom_ids),
            "invalidated_sections": len(refresh.invalidate_section_ids),
        },
        "fixed_500_token_chunks": {
            "before": len(old_fixed),
            "after": len(new_fixed),
            "invalidated": fixed_invalidated,
        },
        "alignment_ms": elapsed_ms,
        "limitations": "One deterministic edit on one public Markdown document; embedding latency and retrieval quality are not measured.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    cases = [
        {
            "case_id": "insert-early-paragraph",
            "operation": "inserted",
            "before_atom_id": None,
            "after_atom_id": atom.atom_id,
            "after_content_hash": atom.content_hash,
            "observed_action": "embed raw and contextual vectors",
        }
        for atom in alignment.inserted
    ]
    cases.extend(
        {
            "case_id": "modify-existing-phrase",
            "operation": "modified",
            "before_atom_id": item.before.atom_id,
            "after_atom_id": item.after.atom_id,
            "before_content_hash": item.before.content_hash,
            "after_content_hash": item.after.content_hash,
            "lexical_similarity": item.lexical_similarity,
            "observed_action": "embed new vectors and tombstone old atom",
        }
        for item in alignment.modified
    )
    cases.append(
        {
            "case_id": "unchanged-atoms",
            "operation": "equal",
            "count": len(alignment.unchanged),
            "observed_action": "reuse raw and contextual vectors",
        }
    )
    cases.append(
        {
            "case_id": "fixed-boundary-comparison",
            "operation": "fixed_500_token_chunks",
            "before": len(old_fixed),
            "after": len(new_fixed),
            "invalidated": fixed_invalidated,
        }
    )
    args.cases.parent.mkdir(parents=True, exist_ok=True)
    args.cases.write_text("".join(json.dumps(case) + "\n" for case in cases))


if __name__ == "__main__":
    main()
