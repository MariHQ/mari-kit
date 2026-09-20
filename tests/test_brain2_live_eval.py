import io
import json
import subprocess
import sys
import urllib.error

import pytest

from examples.company_brains.durable import live_eval
from mari_kit import KnowledgeDocument


def test_fixture_quality_cli_emits_a_complete_report():
    completed = subprocess.run(
        [sys.executable, "-m", "examples.company_brains.durable.quality_eval"],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)
    assert report["mode"] == "fixture"
    assert report["metrics"]["case_count"] == len(report["cases"]) >= 24


def test_live_prompt_whitelists_source_fields_without_grading_labels():
    document = KnowledgeDocument(
        source_id="handbook",
        external_id="refunds",
        title="Refunds",
        body="Refunds require approval.",
        revision="v1",
    )
    payload = live_eval.source_input(
        {
            "id": "secret-label",
            "question": "Who approves refunds?",
            "documents": (document,),
            "required_terms": ["hidden-gold-answer"],
            "forbidden_terms": ["private-grading-rule"],
            "expected_disposition": "insufficient_evidence",
        }
    )
    assert set(payload) == {"question", "documents"}
    encoded = json.dumps(payload)
    assert "hidden-gold-answer" not in encoded
    assert "private-grading-rule" not in encoded
    assert "secret-label" not in encoded
    assert payload["documents"][0]["document_id"] == document.document_id


def test_model_transport_requires_explicit_credential(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        live_eval.request_json("system", {}, model="deepseek-flash")


def test_live_prompt_excludes_restricted_and_superseded_material():
    from dataclasses import replace

    current = KnowledgeDocument(
        source_id="handbook",
        external_id="refunds",
        title="Refunds",
        body="Current approved policy.",
        revision="v2",
    )
    old = replace(
        current, revision="v1", body="Private archived text.", content_digest=""
    )
    case = {
        "question": "Policy?",
        "documents": (old, current),
        "authorized_documents": (current,),
    }
    assert live_eval.source_input(case)["documents"][0]["revision"] == "v2"
    assert "Private archived text" not in json.dumps(live_eval.source_input(case))
    case["authorized_documents"] = ()
    assert live_eval.source_input(case)["documents"] == []


def test_model_http_failure_does_not_include_provider_body_or_credential(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-secret")

    def reject(*args, **kwargs):
        raise urllib.error.HTTPError(
            "https://api.deepseek.com/chat/completions",
            429,
            "provider-body-with-secret",
            {},
            io.BytesIO(b"test-only-secret"),
        )

    monkeypatch.setattr(live_eval.urllib.request, "urlopen", reject)
    with pytest.raises(RuntimeError) as caught:
        live_eval.request_json("system", {}, model="deepseek-flash")
    assert str(caught.value) == "model HTTP status 429"


@pytest.mark.parametrize("finish_reason", ["length", "content_filter"])
def test_truncated_model_responses_are_not_graded_as_complete(
    monkeypatch, finish_reason
):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-secret")
    envelope = {
        "choices": [{"finish_reason": finish_reason, "message": {"content": "{}"}}]
    }
    monkeypatch.setattr(
        live_eval.urllib.request,
        "urlopen",
        lambda *args, **kwargs: io.BytesIO(json.dumps(envelope).encode()),
    )
    with pytest.raises(ValueError, match="incomplete model response"):
        live_eval.request_json("system", {}, model="deepseek-flash")
