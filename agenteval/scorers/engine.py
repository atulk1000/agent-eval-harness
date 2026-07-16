"""Run-level scoring orchestration."""

from __future__ import annotations

from typing import Any

from agenteval.claim_eval.pipeline import ClaimEvaluationConfig
from agenteval.scorers.efficiency import score_efficiency, score_trace_errors
from agenteval.scorers.facts import score_expected_facts
from agenteval.scorers.judges import score_judges
from agenteval.scorers.retrieval import score_retrieval
from agenteval.scorers.sql_correctness import score_sql_correctness
from agenteval.scorers.tool_routing import score_tool_routing


def score_run(
    task: dict[str, Any],
    run: dict[str, Any],
    claim_config: ClaimEvaluationConfig | None = None,
) -> dict[str, Any]:
    tool = score_tool_routing(task, run)
    sql = score_sql_correctness(task, run)
    retrieval = score_retrieval(task, run)
    facts = score_expected_facts(task, run)
    efficiency = score_efficiency(task, run)
    trace_errors = score_trace_errors(run)
    judges = score_judges(task, run, facts["score"], claim_config)

    dimension_scores = {
        "tool_routing": tool["score"],
        "sql_correctness": sql["score"],
        "retrieval_grounding": retrieval["score"],
        "faithfulness": judges["faithfulness_score"],
        "completeness": judges["completeness_score"],
        "synthesis": judges["synthesis_score"],
        "source_attribution": judges["source_attribution_score"],
        "expected_facts": facts["score"],
        "efficiency": efficiency["score"],
        "trace_health": trace_errors["score"],
    }
    rubric = task.get("rubric", {})
    weighted_total = 0.0
    weight_total = 0.0
    for dimension, weight in rubric.items():
        if weight <= 0:
            continue
        score = dimension_scores.get(dimension)
        if score is None:
            continue
        weighted_total += score * float(weight)
        weight_total += float(weight)
    applicable_scores = [value for value in dimension_scores.values() if value is not None]
    overall = (
        weighted_total / weight_total
        if weight_total
        else sum(applicable_scores) / max(len(applicable_scores), 1)
    )
    faithfulness_status = judges["faithfulness_status"]
    if faithfulness_status == "fail":
        status = "fail"
    elif faithfulness_status == "needs_review":
        status = "needs_review"
    else:
        status = "pass" if overall >= 0.8 else "fail"

    failure_labels = _dedupe(
        tool.get("failure_labels", [])
        + sql.get("failure_labels", [])
        + retrieval.get("failure_labels", [])
        + facts.get("failure_labels", [])
        + efficiency.get("failure_labels", [])
        + trace_errors.get("failure_labels", [])
        + judges.get("failure_labels", [])
    )
    return {
        "task_id": task["id"],
        "task_type": task["task_type"],
        "overall_score": round(overall, 3),
        "status": status,
        "dimension_scores": dimension_scores,
        "tool_routing": tool,
        "sql_correctness": sql,
        "retrieval": retrieval,
        "expected_facts": facts,
        "efficiency": efficiency,
        "trace_errors": trace_errors,
        "judges": judges,
        "claim_evaluation": judges["claim_evaluation"],
        "unsupported_claims": judges["unsupported_claims"],
        "failure_labels": failure_labels,
    }


def _dedupe(labels: list[str]) -> list[str]:
    seen = set()
    result = []
    for label in labels:
        if label and label not in seen:
            result.append(label)
            seen.add(label)
    return result
