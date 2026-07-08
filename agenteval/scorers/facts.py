"""Expected answer fact and term scorer."""

from __future__ import annotations

from typing import Any

from agenteval.scorers.common import contains_term


def score_expected_facts(task: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    terms = task.get("expected_answer_terms", [])
    if not terms:
        return {"score": 1.0, "missing_terms": [], "matched_terms": []}
    answer = run.get("final_answer", "")
    matched = [term for term in terms if contains_term(answer, term)]
    missing = [term for term in terms if term not in matched]
    return {
        "score": round(len(matched) / len(terms), 3),
        "matched_terms": matched,
        "missing_terms": missing,
        "failure_labels": ["missing_expected_answer_fact"] if missing else [],
    }
