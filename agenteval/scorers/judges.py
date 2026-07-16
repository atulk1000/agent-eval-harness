"""Claim evaluation plus the remaining v1.2 heuristic dimensions."""

from __future__ import annotations

from typing import Any

from agenteval.claim_eval.pipeline import ClaimEvaluationConfig, evaluate_run_claims
from agenteval.scorers.common import actual_route, contains_term


def score_judges(
    task: dict[str, Any],
    run: dict[str, Any],
    fact_score: float,
    claim_config: ClaimEvaluationConfig | None = None,
) -> dict[str, Any]:
    claim_evaluation = evaluate_run_claims(task, run, claim_config)
    claim_lookup = {claim["claim_id"]: claim for claim in claim_evaluation["claims"]}
    issues = []
    for verdict in claim_evaluation["verdicts"]:
        if verdict["severity"] == "none":
            continue
        claim = claim_lookup[verdict["claim_id"]]
        issues.append(
            {
                "claim_id": verdict["claim_id"],
                "claim": claim["text"],
                "verdict": verdict["verdict"],
                "severity": verdict["severity"],
                "reason": verdict["reason"],
                "evidence_refs": verdict["evidence_refs"],
            }
        )
    completeness = fact_score
    synthesis = _synthesis_score(task, run, issues)
    source_attribution = _source_attribution_score(task, run)
    return {
        "faithfulness_score": claim_evaluation["metrics"]["score"],
        "faithfulness_status": claim_evaluation["metrics"]["status"],
        "completeness_score": round(completeness, 3),
        "synthesis_score": round(synthesis, 3),
        "source_attribution_score": round(source_attribution, 3),
        "unsupported_claims": issues,
        "claim_evaluation": claim_evaluation,
        "failure_labels": _failure_labels(issues, task, run, claim_evaluation["metrics"]),
    }


def _synthesis_score(
    task: dict[str, Any], run: dict[str, Any], unsupported: list[dict[str, Any]]
) -> float:
    if task.get("task_type") != "hybrid_sql_rag":
        return 1.0
    route = set(actual_route(run))
    uses_both = "sql_query" in route and "rag_search" in route
    score = 0.55 if uses_both else 0.2
    answer = run.get("final_answer", "")
    entity_terms = task.get("expected_sql", {}).get("expected_entities", [])
    entity_score = 0.0
    if entity_terms:
        entity_score = sum(1 for entity in entity_terms if contains_term(answer, entity)) / len(
            entity_terms
        )
    score += entity_score * 0.30
    if not unsupported:
        score += 0.15
    return min(1.0, score)


def _source_attribution_score(task: dict[str, Any], run: dict[str, Any]) -> float:
    if task.get("task_type") != "hybrid_sql_rag":
        return 1.0
    answer = run.get("final_answer", "").lower()
    structured = any(term in answer for term in ["sql", "invoice data", "data shows"])
    unstructured = any(
        term in answer for term in ["account note", "policy", "support context", "based on"]
    )
    if structured and unstructured:
        return 1.0
    if structured or unstructured:
        return 0.5
    return 0.0


def _failure_labels(
    unsupported: list[dict[str, Any]],
    task: dict[str, Any],
    run: dict[str, Any],
    claim_metrics: dict[str, Any],
) -> list[str]:
    labels: list[str] = []
    if unsupported:
        labels.append("unsupported_claim")
    if claim_metrics.get("status") == "needs_review":
        labels.append("claim_needs_review")
    if task.get("task_type") == "hybrid_sql_rag":
        route = set(actual_route(run))
        if "sql_query" not in route:
            labels.append("missing_structured_evidence")
        if "rag_search" not in route:
            labels.append("missing_unstructured_evidence")
        if any(claim.get("severity") == "high" for claim in unsupported):
            labels.append("overstated_synthesis")
    return labels
