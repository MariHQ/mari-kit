"""Extract candidates → review policy → digest, with no persistence object."""

from __future__ import annotations

import json
import os
from typing import Mapping

from mari_components import KnowledgeDocument
from mari_components.knowledge import (
    ReviewItem, evaluate_approval, extract_decisions, extract_facts,
    harvest_glossary, mine_answers, summarize_digest,
)

from examples.support import json_generator


DOCUMENT = KnowledgeDocument(
    "runbook", "Release runbook",
    "Mari deploys the tested main branch. A release requires two reviewers. "
    "Grounded Answer means an answer with exact source evidence.",
    revision="v3",
)


def _fixture(_prompt: str, version: str) -> object:
    release_evidence = [{
        "document_id": "runbook", "quote": "Mari deploys the tested main branch.",
    }]
    if version == "facts-extract-v2":
        return {"facts": [{
            "claim": "Mari deploys the tested main branch.",
            "evidence": release_evidence,
        }]}
    if version == "decisions-extract-v2":
        return {"decisions": [{
            "statement": "Releases use the tested main branch.",
            "evidence": release_evidence,
        }]}
    if version == "glossary-harvest-v1":
        return {"terms": [{
            "term": "Grounded Answer",
            "definition": "An answer with exact source evidence.",
            "aliases": ["grounded response"],
            "evidence": [{
                "document_id": "runbook",
                "quote": "Grounded Answer means an answer with exact source evidence.",
            }],
        }]}
    if version == "faq-mine-v2":
        return {"answers": [{
            "question": "How is Mari released?", "answer": "Deploy the tested main branch.",
            "evidence": release_evidence,
        }]}
    if version == "digest-summary-v1":
        return {
            "summary": "The release process is documented.",
            "topics": [{
                "title": "Release", "summary": "Deploy tested main.",
                "evidence": release_evidence,
            }],
            "evidence": release_evidence,
        }
    raise AssertionError(f"unexpected recipe: {version}")


def run(environment: Mapping[str, str] | None = None) -> dict[str, object]:
    env = os.environ if environment is None else environment
    generate = json_generator(env, _fixture)
    facts = extract_facts((DOCUMENT,), generate_json=generate)
    decisions = extract_decisions((DOCUMENT,), generate_json=generate)
    glossary = harvest_glossary((DOCUMENT,), generate_json=generate)
    answers = mine_answers((DOCUMENT,), generate_json=generate)
    digest = summarize_digest((DOCUMENT,), generate_json=generate)
    approval = evaluate_approval(ReviewItem(
        "fact:1", "fact", proposer_id="user:author",
        confidence=facts[0].confidence,
        evidence_count=len(facts[0].evidence),
        trusted_source=True,
    ), "user:reviewer")
    return {
        "facts": len(facts),
        "decisions": len(decisions),
        "glossary_terms": len(glossary),
        "faq_answers": len(answers),
        "digest_topics": len(digest.topics),
        "approval": approval.outcome,
        "approval_explanation": approval.explanation,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
