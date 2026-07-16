"""Risk-weighted claim-faithfulness scoring and hard gates."""

from __future__ import annotations

from collections import Counter
from typing import Any

from agenteval.claim_eval.severity import RISK_WEIGHTS

VERDICT_VALUES = {
    "supported": 1.0,
    "partially_supported": 0.5,
    "unsupported": 0.0,
    "contradicted": 0.0,
    "not_enough_evidence": 0.0,
}


def aggregate_claim_scores(
    claims: list[dict[str, Any]], verdicts: list[dict[str, Any]]
) -> dict[str, Any]:
    if not claims:
        return {
            "score": None,
            "status": "not_applicable",
            "claim_count": 0,
            "verdict_counts": {},
            "issue_count": 0,
            "high_severity_issue_count": 0,
            "hard_gate_failures": [],
            "needs_review_count": 0,
        }
    claim_lookup = {claim["claim_id"]: claim for claim in claims}
    numerator = 0.0
    denominator = 0.0
    hard_gates: list[str] = []
    needs_review = 0
    for verdict in verdicts:
        claim = claim_lookup[verdict["claim_id"]]
        weight = RISK_WEIGHTS[verdict["risk_level"]]
        value = VERDICT_VALUES[verdict["verdict"]]
        if (
            verdict["verdict"] == "not_enough_evidence"
            and claim.get("assertion_mode") in {"caveated", "uncertain"}
            and verdict["severity"] == "none"
        ):
            value = 1.0
        numerator += value * weight
        denominator += weight
        if verdict.get("requires_review") and verdict["risk_level"] in {"medium", "high"}:
            needs_review += 1
        if verdict["severity"] == "high" and verdict["verdict"] in {
            "unsupported",
            "contradicted",
            "not_enough_evidence",
        }:
            hard_gates.append(verdict["claim_id"])
    score = round(numerator / denominator, 3) if denominator else None
    if hard_gates:
        status = "fail"
    elif needs_review:
        status = "needs_review"
    else:
        status = "pass" if score is not None and score >= 0.8 else "fail"
    counts = Counter(verdict["verdict"] for verdict in verdicts)
    issues = [verdict for verdict in verdicts if verdict["severity"] != "none"]
    return {
        "score": score,
        "status": status,
        "claim_count": len(claims),
        "verdict_counts": dict(sorted(counts.items())),
        "issue_count": len(issues),
        "high_severity_issue_count": sum(1 for verdict in issues if verdict["severity"] == "high"),
        "hard_gate_failures": hard_gates,
        "needs_review_count": needs_review,
    }
