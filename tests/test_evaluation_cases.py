import json

from mari_components.evaluation import (
    load_beir_cases,
    load_fever_cases,
    load_longmemeval_cases,
)


def test_beir_adapter_joins_queries_and_graded_qrels(tmp_path) -> None:
    queries = tmp_path / "queries.jsonl"
    queries.write_text('{"_id":"q1","text":"refund"}\n')
    qrels = tmp_path / "qrels.tsv"
    qrels.write_text("query-id\tcorpus-id\tscore\nq1\td1\t2\n")

    cases = load_beir_cases(queries, qrels)
    assert cases[0].query == "refund"
    assert dict(cases[0].relevance) == {"d1": 2.0}


def test_fever_adapter_preserves_evidence_line_identity(tmp_path) -> None:
    path = tmp_path / "fever.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": 1,
                "claim": "claim",
                "label": "SUPPORTS",
                "evidence": [[[0, 0, "Page", 4]]],
            }
        )
        + "\n"
    )
    case = load_fever_cases(path)[0]
    assert case.evidence_ids == ("Page#4",)


def test_longmemeval_adapter_drops_answer_side_channels(tmp_path) -> None:
    path = tmp_path / "memory.json"
    path.write_text(
        json.dumps(
            [
                {
                    "question_id": "q1",
                    "question": "Where?",
                    "answer": "Rome",
                    "question_type": "temporal",
                    "haystack_sessions": [["hello"]],
                    "answer_session_ids": ["session-4"],
                    "source": "cleaned",
                }
            ]
        )
    )
    case = load_longmemeval_cases(path)[0]
    assert "answer_session_ids" not in case.metadata
    assert case.sessions == (["hello"],)
