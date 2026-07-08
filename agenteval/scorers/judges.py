"""Mock judge layer for semantic scoring and unsupported claims."""

from __future__ import annotations

import re
from typing import Any

from agenteval.scorers.common import actual_route, contains_term, evidence_text


SEVERITY_PENALTY = {"low": 0.1, "medium": 0.25, "high": 0.45}


def detect_unsupported_claims(task: dict[str, Any], run: dict[str, Any]) -> list[dict[str, Any]]:
    answer = run.get("final_answer", "")
    evidence = evidence_text(run)
    claims = []
    for trap in task.get("unsupported_claim_traps", []):
        pattern = trap.get("pattern")
        if not pattern:
            continue
        match = re.search(pattern, answer, flags=re.IGNORECASE)
        if match and not _is_negated_or_caveated(answer, match.start()):
            # If the same literal pattern appears in evidence, downgrade to partial support.
            verdict = "unsupported"
            if re.search(pattern, evidence, flags=re.IGNORECASE):
                verdict = "partially_supported"
            claims.append(
                {
                    "claim": trap.get("claim", pattern),
                    "verdict": verdict,
                    "severity": trap.get("severity", "medium"),
                    "reason": trap.get("reason", "No trace evidence supports this claim."),
                    "evidence_refs": [],
                }
            )
    return claims


def _is_negated_or_caveated(answer: str, match_start: int) -> bool:
    """Return True when a risky phrase is part of a caution, not a claim."""

    prefix = answer[max(0, match_start - 120) : match_start].lower()
    caveats = [
        "no evidence",
        "found no evidence",
        "do not see evidence",
        "does not show",
        "do not show",
        "does not say",
        "not say",
        "not confirmed",
        "without evidence",
        "no trace evidence",
    ]
    return any(caveat in prefix for caveat in caveats)


def score_judges(task: dict[str, Any], run: dict[str, Any], fact_score: float) -> dict[str, Any]:
    unsupported = detect_unsupported_claims(task, run)
    penalty = sum(SEVERITY_PENALTY.get(claim["severity"], 0.25) for claim in unsupported)
    faithfulness = max(0.0, 1.0 - penalty)
    completeness = fact_score
    synthesis = _synthesis_score(task, run, unsupported)
    source_attribution = _source_attribution_score(task, run)
    return {
        "faithfulness_score": round(faithfulness, 3),
        "completeness_score": round(completeness, 3),
        "synthesis_score": round(synthesis, 3),
        "source_attribution_score": round(source_attribution, 3),
        "unsupported_claims": unsupported,
        "failure_labels": _failure_labels(unsupported, task, run),
    }


def _synthesis_score(task: dict[str, Any], run: dict[str, Any], unsupported: list[dict[str, Any]]) -> float:
    if task.get("task_type") != "hybrid_sql_rag":
        return 1.0
    route = set(actual_route(run))
    uses_both = "sql_query" in route and "rag_search" in route
    score = 0.55 if uses_both else 0.2
    answer = run.get("final_answer", "")
    entity_terms = task.get("expected_sql", {}).get("expected_entities", [])
    entity_score = 0.0
    if entity_terms:
        entity_score = sum(1 for entity in entity_terms if contains_term(answer, entity)) / len(entity_terms)
    score += entity_score * 0.30
    if not unsupported:
        score += 0.15
    return min(1.0, score)


def _source_attribution_score(task: dict[str, Any], run: dict[str, Any]) -> float:
    if task.get("task_type") != "hybrid_sql_rag":
        return 1.0
    answer = run.get("final_answer", "").lower()
    structured = any(term in answer for term in ["sql", "invoice data", "data shows"])
    unstructured = any(term in answer for term in ["account note", "policy", "support context", "based on"])
    if structured and unstructured:
        return 1.0
    if structured or unstructured:
        return 0.5
    return 0.0


def _failure_labels(
    unsupported: list[dict[str, Any]], task: dict[str, Any], run: dict[str, Any]
) -> list[str]:
    labels: list[str] = []
    if unsupported:
        labels.append("unsupported_claim")
    if task.get("task_type") == "hybrid_sql_rag":
        route = set(actual_route(run))
        if "sql_query" not in route:
            labels.append("missing_structured_evidence")
        if "rag_search" not in route:
            labels.append("missing_unstructured_evidence")
        if any(claim.get("severity") == "high" for claim in unsupported):
            labels.append("overstated_synthesis")
    return labels
