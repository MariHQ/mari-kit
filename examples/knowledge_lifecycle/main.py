"""Extract evidence-linked candidates and invalidate them on source edits."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping

from examples.support import json_generator
from mari_components import KnowledgeDocument
from mari_components.knowledge import (
    assess_freshness,
    parse_answer_candidates,
    parse_decisions,
    parse_digest,
    parse_facts,
    parse_glossary,
)

DOCUMENT = KnowledgeDocument(
    source_id="handbook",
    external_id="runbook",
    title="Release runbook",
    body="Mari deploys the tested main branch. A release requires two reviewers. "
    "Grounded Answer means an answer with exact source evidence.",
    revision="v3",
)


def _fixture(_prompt: str, version: str) -> object:
    release_evidence = [
        {
            "document_id": "handbook/runbook",
            "quote": "Mari deploys the tested main branch.",
        }
    ]
    if version == "facts-extract-v2":
        return {
            "facts": [
                {
                    "claim": "Mari deploys the tested main branch.",
                    "evidence": release_evidence,
                }
            ]
        }
    if version == "decisions-extract-v2":
        return {
            "decisions": [
                {
                    "statement": "Releases use the tested main branch.",
                    "evidence": release_evidence,
                }
            ]
        }
    if version == "glossary-harvest-v1":
        return {
            "terms": [
                {
                    "term": "Grounded Answer",
                    "definition": "An answer with exact source evidence.",
                    "aliases": ["grounded response"],
                    "evidence": [
                        {
                            "document_id": "handbook/runbook",
                            "quote": "Grounded Answer means an answer with exact source evidence.",
                        }
                    ],
                }
            ]
        }
    if version == "faq-mine-v2":
        return {
            "answers": [
                {
                    "question": "How is Mari released?",
                    "answer": "Deploy the tested main branch.",
                    "evidence": release_evidence,
                }
            ]
        }
    if version == "digest-summary-v1":
        return {
            "summary": "The release process is documented.",
            "topics": [
                {
                    "title": "Release",
                    "summary": "Deploy tested main.",
                    "evidence": release_evidence,
                }
            ],
            "evidence": release_evidence,
        }
    raise AssertionError(f"unexpected recipe: {version}")


def run(environment: Mapping[str, str] | None = None) -> dict[str, object]:
    env = os.environ if environment is None else environment
    generate = json_generator(env, _fixture)
    context = json.dumps(
        {
            "document_id": DOCUMENT.document_id,
            "revision": DOCUMENT.revision,
            "title": DOCUMENT.title,
            "body": DOCUMENT.body,
        }
    )

    def model(task: str, schema: str, version: str) -> object:
        return generate(
            f"{task} Return JSON matching {schema}. Document: {context}",
            version,
        )

    facts = parse_facts(
        (DOCUMENT,),
        model(
            "Extract atomic facts with exact quotes.",
            '{"facts":[{"claim":"...","evidence":[{"document_id":"...","quote":"..."}]}]}',
            "facts-extract-v2",
        ),
    )
    decisions = parse_decisions(
        (DOCUMENT,),
        model(
            "Extract explicit decisions with exact quotes.",
            '{"decisions":[{"statement":"...","evidence":[...]}]}',
            "decisions-extract-v2",
        ),
    )
    glossary = parse_glossary(
        (DOCUMENT,),
        model(
            "Extract organization-specific terms with exact quotes.",
            '{"terms":[{"term":"...","definition":"...","aliases":[],"evidence":[...]}]}',
            "glossary-harvest-v1",
        ),
    )
    answers = parse_answer_candidates(
        (DOCUMENT,),
        model(
            "Extract directly answered questions with exact quotes.",
            '{"answers":[{"question":"...","answer":"...","evidence":[...]}]}',
            "faq-mine-v2",
        ),
    )
    digest = parse_digest(
        (DOCUMENT,),
        model(
            "Summarize the document with exact evidence.",
            '{"summary":"...","topics":[{"title":"...","summary":"...","evidence":[...]}],"evidence":[...]}',
            "digest-summary-v1",
        ),
    )
    current = assess_freshness(facts[0].evidence, {"handbook/runbook": "v3"})
    after_edit = assess_freshness(facts[0].evidence, {"handbook/runbook": "v4"})
    return {
        "facts": len(facts),
        "decisions": len(decisions),
        "glossary_terms": len(glossary),
        "faq_answers": len(answers),
        "digest_topics": len(digest.topics),
        "initial_freshness": current.status.value,
        "freshness_after_source_edit": after_edit.status.value,
        "stale_fact_reusable": after_edit.reusable,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
