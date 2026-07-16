"""Deterministic risk and issue-severity policy."""

from __future__ import annotations

from typing import Any

RISK_WEIGHTS = {"low": 1, "medium": 2, "high": 4}


class SeverityPolicy:
    def risk_level(self, claim: dict[str, Any], task: dict[str, Any]) -> str:
        claim_type = claim.get("claim_type")
        lowered = str(claim.get("text", "")).lower()
        if claim_type in {"numeric", "business_status", "policy_or_requirement"}:
            return "high"
        if any(
            term in lowered for term in ("approval", "churn", "contract", "terminated", "at risk")
        ):
            return "high"
        if claim_type in {"causal", "comparative", "source_attribution"}:
            return "medium"
        domain_risk = task.get("domain_risk", {})
        configured = domain_risk.get(claim_type) if isinstance(domain_risk, dict) else None
        return configured if configured in RISK_WEIGHTS else "low"

    def apply(self, claim: dict[str, Any], verdict: str, risk_level: str) -> tuple[str, str]:
        if verdict == "supported":
            return "none", "The claim is supported; potential risk remains available for weighting."
        if (
            claim.get("assertion_mode") in {"caveated", "uncertain"}
            and verdict == "not_enough_evidence"
        ):
            return "none", "The answer appropriately communicates evidence uncertainty."
        if verdict == "partially_supported":
            severity = "medium" if risk_level == "high" else "low"
            return severity, "A material part of the claim is not supported."
        if verdict == "contradicted":
            severity = "high" if risk_level in {"medium", "high"} else "medium"
            return severity, "Available trace evidence conflicts with the claim."
        return risk_level, "The asserted claim is not established by the available trace evidence."
