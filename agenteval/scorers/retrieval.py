"""RAG retrieval scorer."""

from __future__ import annotations

from typing import Any

from agenteval.scorers.common import retrieved_doc_ids


def score_retrieval(task: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    expected = set(task.get("expected_documents", {}).get("relevant_doc_ids", []))
    seen = retrieved_doc_ids(run)
    if not expected:
        return {
            "score": 1.0,
            "applicable": False,
            "expected_docs_found": [],
            "missing_docs": [],
            "irrelevant_docs": sorted(seen),
            "failure_labels": [],
        }
    found = expected & seen
    missing = expected - seen
    irrelevant = seen - expected
    recall = len(found) / len(expected)
    precision = 1.0 if not seen else len(found) / len(seen)
    labels = []
    if missing:
        labels.append("missing_relevant_document")
    score = recall * 0.75 + precision * 0.25
    return {
        "score": round(score, 3),
        "applicable": True,
        "expected_docs_found": sorted(found),
        "missing_docs": sorted(missing),
        "irrelevant_docs": sorted(irrelevant),
        "failure_labels": labels,
    }
