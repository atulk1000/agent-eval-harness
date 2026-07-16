"""Deterministic-first composite claim judgment."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

from agenteval.claim_eval.cache import JudgeCache, cache_key
from agenteval.claim_eval.models import (
    SCHEMA_VERSION,
    VERDICTS,
    RecordValidationError,
    stable_id,
    validate_judge_call,
    validate_verdict,
)
from agenteval.claim_eval.providers import (
    PROMPT_VERSION,
    JudgeProviderError,
    JudgeProviderTimeout,
    RuleOnlyJudgeProvider,
    SemanticJudgeProvider,
)
from agenteval.claim_eval.severity import SeverityPolicy

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "which",
    "with",
    "supplied",
    "result",
    "shows",
    "showed",
}


@dataclass
class JudgeBudget:
    max_calls: int = 50
    max_evidence_characters: int = 12000
    calls_used: int = 0

    def consume(self) -> bool:
        if self.calls_used >= self.max_calls:
            return False
        self.calls_used += 1
        return True


class DeterministicClaimJudge:
    def __init__(self, numeric_tolerance: float = 0.01) -> None:
        self.numeric_tolerance = numeric_tolerance

    def judge(self, claim: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
        positive = [
            item for item in evidence if item["source_type"] not in {"tool_error", "empty_result"}
        ]
        diagnostics = [
            item for item in evidence if item["source_type"] in {"tool_error", "empty_result"}
        ]
        refs = [item["evidence_id"] for item in positive]
        if not positive:
            reason = "No usable trace evidence is available for this claim."
            if diagnostics:
                reason = "Tool failure or empty output left insufficient evidence for this claim."
            return _result("not_enough_evidence", 0.99, reason, [], [], True)

        if not _has_required_source(claim, positive):
            return _result(
                "not_enough_evidence",
                0.98,
                "The trace does not contain the source type required to evaluate this claim.",
                refs,
                [],
                True,
            )

        combined = " ".join(_evidence_text(item) for item in positive)
        if _is_evidence_caveat(claim):
            underlying = _caveat_subject(str(claim["text"]))
            if underlying and _normalize(underlying) in _normalize(combined):
                return _result(
                    "contradicted",
                    0.92,
                    "The answer says evidence is absent, but the trace contains the stated fact.",
                    refs,
                    [underlying],
                    True,
                    structured=True,
                )
            return _result(
                "supported",
                0.9,
                "The trace does not establish the positive fact, matching the answer's caveat.",
                refs,
                [],
                True,
            )

        structured_conflict = _structured_conflict(claim, positive, self.numeric_tolerance)
        if structured_conflict:
            return _result(
                "contradicted",
                0.99,
                structured_conflict,
                refs,
                _numbers(str(claim["text"])),
                True,
                structured=True,
            )

        claim_numbers = _numbers(str(claim["text"]))
        evidence_numbers = _numbers(combined)
        missing_numbers = [
            number
            for number in claim_numbers
            if not _number_present(number, evidence_numbers, self.numeric_tolerance)
        ]
        coverage = _coverage(str(claim["text"]), combined)
        if missing_numbers and coverage >= 0.45:
            return _result(
                "partially_supported",
                0.91,
                "The core claim matches the trace, but one or more numeric details are not supported.",
                refs,
                missing_numbers,
                True,
            )
        subject = str(claim.get("subject") or "").lower()
        subject_present = not subject or subject in combined.lower()
        if not missing_numbers and (
            coverage >= 0.62
            or _normalize(str(claim["text"])) in _normalize(combined)
            or (claim.get("claim_type") == "numeric" and subject_present and coverage >= 0.35)
        ):
            return _result(
                "supported",
                min(0.99, 0.72 + coverage / 3),
                "The material entities and details are present in the selected trace evidence.",
                refs,
                [],
                True,
            )
        if coverage >= 0.4:
            return _result(
                "partially_supported",
                0.76,
                "The evidence supports the core topic but not every material qualifier.",
                refs,
                _unsupported_terms(str(claim["text"]), combined),
                True,
            )
        if coverage >= 0.12:
            return _result(
                "not_enough_evidence",
                0.55,
                "The trace contains related evidence, but semantic interpretation is required.",
                refs,
                _unsupported_terms(str(claim["text"]), combined),
                False,
            )
        return _result(
            "unsupported",
            0.9,
            "Relevant trace evidence exists but does not support the asserted fact.",
            refs,
            _unsupported_terms(str(claim["text"]), combined),
            True,
        )


class CompositeClaimJudge:
    def __init__(
        self,
        provider: SemanticJudgeProvider | None = None,
        *,
        cache: JudgeCache | None = None,
        budget: JudgeBudget | None = None,
        severity_policy: SeverityPolicy | None = None,
    ) -> None:
        self.provider = provider or RuleOnlyJudgeProvider()
        self.cache = cache or JudgeCache()
        self.budget = budget or JudgeBudget()
        self.severity_policy = severity_policy or SeverityPolicy()
        self.deterministic = DeterministicClaimJudge()

    def judge(
        self,
        claim: dict[str, Any],
        evidence: list[dict[str, Any]],
        task: dict[str, Any],
        selection: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        deterministic = self.deterministic.judge(claim, evidence)
        calls: list[dict[str, Any]] = []
        chosen = deterministic
        judge_path = (
            "deterministic_precedence" if deterministic.get("structured") else "deterministic"
        )
        requires_review = False

        if not deterministic["resolved"]:
            if isinstance(self.provider, RuleOnlyJudgeProvider):
                judge_path = "unresolved"
                requires_review = True
            else:
                semantic, call = self._semantic(claim, evidence)
                calls.append(call)
                if semantic is None:
                    judge_path = "unresolved"
                    requires_review = True
                else:
                    chosen = semantic
                    judge_path = "semantic"

        risk = self.severity_policy.risk_level(claim, task)
        severity, severity_reason = self.severity_policy.apply(claim, chosen["verdict"], risk)
        verdict = {
            "schema_version": SCHEMA_VERSION,
            "claim_id": claim["claim_id"],
            "run_id": claim["run_id"],
            "task_id": claim["task_id"],
            "verdict": chosen["verdict"],
            "confidence": round(float(chosen["confidence"]), 3),
            "reason": chosen["reason"],
            "evidence_refs": chosen.get("evidence_refs", []),
            "evidence_considered": [item["evidence_id"] for item in evidence],
            "unsupported_parts": chosen.get("unsupported_parts", []),
            "judge_path": judge_path,
            "risk_level": risk,
            "severity": severity,
            "severity_reason": severity_reason,
            "requires_review": requires_review,
            "selection": selection,
        }
        return validate_verdict(verdict), calls

    def _semantic(
        self, claim: dict[str, Any], evidence: list[dict[str, Any]]
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        provider = self.provider
        limited_evidence = _limit_evidence(evidence, self.budget.max_evidence_characters)
        key = cache_key(
            claim,
            limited_evidence,
            provider=provider.name,
            model=provider.model,
            prompt_version=PROMPT_VERSION,
        )
        call_id = stable_id("judge", claim["claim_id"], key)
        cached = self.cache.get(key)
        if cached is not None:
            return self._validate_semantic(cached, limited_evidence), self._call_record(
                call_id, claim, key, "success", cache_hit=True
            )
        if not self.budget.consume():
            return None, self._call_record(
                call_id,
                claim,
                key,
                "budget_exhausted",
                error="Semantic call budget exhausted.",
            )

        started = time.perf_counter()
        try:
            response = provider.judge(claim, limited_evidence)
            latency = int((time.perf_counter() - started) * 1000)
            output = self._validate_semantic(response.output, limited_evidence)
            self.cache.put(key, response.output)
            call = self._call_record(
                call_id,
                claim,
                key,
                "success",
                latency_ms=latency,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                estimated_cost=response.estimated_cost,
                redacted=response.redacted,
                attempts=response.attempts,
            )
            return output, call
        except JudgeProviderTimeout as exc:
            status = "timeout"
            error = str(exc)
        except (JudgeProviderError, RecordValidationError, ValueError, TypeError) as exc:
            status = "invalid_output" if not isinstance(exc, JudgeProviderError) else "error"
            error = str(exc)
        latency = int((time.perf_counter() - started) * 1000)
        return None, self._call_record(call_id, claim, key, status, latency_ms=latency, error=error)

    def _validate_semantic(
        self, output: dict[str, Any], evidence: list[dict[str, Any]]
    ) -> dict[str, Any]:
        if not isinstance(output, dict) or output.get("verdict") not in VERDICTS:
            raise RecordValidationError("semantic output has an invalid verdict")
        confidence = output.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise RecordValidationError("semantic output has invalid confidence")
        if not isinstance(output.get("reason"), str) or not output["reason"].strip():
            raise RecordValidationError("semantic output has no reason")
        valid_refs = {item["evidence_id"] for item in evidence}
        refs = output.get("evidence_refs", [])
        if not isinstance(refs, list) or not set(refs) <= valid_refs:
            raise RecordValidationError(
                "semantic output references evidence outside the candidate set"
            )
        return {
            "verdict": output["verdict"],
            "confidence": float(confidence),
            "reason": output["reason"],
            "evidence_refs": refs,
            "unsupported_parts": output.get("unsupported_parts", []),
            "resolved": True,
        }

    def _call_record(
        self,
        call_id: str,
        claim: dict[str, Any],
        key: str,
        status: str,
        *,
        cache_hit: bool = False,
        latency_ms: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        estimated_cost: float = 0.0,
        redacted: bool = False,
        attempts: int = 0,
        error: str | None = None,
    ) -> dict[str, Any]:
        return validate_judge_call(
            {
                "schema_version": SCHEMA_VERSION,
                "judge_call_id": call_id,
                "claim_id": claim["claim_id"],
                "provider": self.provider.name,
                "model": self.provider.model,
                "prompt_version": PROMPT_VERSION,
                "temperature": 0,
                "cache_key": key,
                "cache_hit": cache_hit,
                "latency_ms": latency_ms,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost": estimated_cost,
                "redacted": redacted,
                "attempts": attempts,
                "status": status,
                "error": error,
            }
        )


def _result(
    verdict: str,
    confidence: float,
    reason: str,
    evidence_refs: list[str],
    unsupported_parts: list[str],
    resolved: bool,
    *,
    structured: bool = False,
) -> dict[str, Any]:
    return {
        "verdict": verdict,
        "confidence": confidence,
        "reason": reason,
        "evidence_refs": evidence_refs,
        "unsupported_parts": unsupported_parts,
        "resolved": resolved,
        "structured": structured,
    }


def _has_required_source(claim: dict[str, Any], evidence: list[dict[str, Any]]) -> bool:
    types = {item["source_type"] for item in evidence}
    requirement = claim.get("source_requirement")
    if requirement == "sql":
        return "sql_row" in types
    if requirement == "rag":
        return bool(types & {"document_chunk", "opened_document"})
    if requirement == "hybrid":
        return "sql_row" in types and bool(types & {"document_chunk", "opened_document"})
    return True


def _evidence_text(item: dict[str, Any]) -> str:
    tool_input = item.get("provenance", {}).get("tool_input")
    return " ".join(
        [
            str(item.get("content", "")),
            json.dumps(item.get("structured_payload", {}), sort_keys=True),
            json.dumps(tool_input, sort_keys=True) if tool_input else "",
        ]
    )


def _tokens(text: str) -> set[str]:
    raw = re.findall(r"[a-z0-9]+", text.lower().replace("_", " "))
    return {_stem(token) for token in raw if token not in STOPWORDS and len(token) > 1}


def _stem(token: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) > len(suffix) + 3:
            return token[: -len(suffix)]
    return token


def _coverage(claim_text: str, evidence_text: str) -> float:
    claim_tokens = _tokens(claim_text)
    return len(claim_tokens & _tokens(evidence_text)) / max(len(claim_tokens), 1)


def _unsupported_terms(claim_text: str, evidence_text: str) -> list[str]:
    return sorted(_tokens(claim_text) - _tokens(evidence_text))[:8]


def _numbers(text: str) -> list[str]:
    return re.findall(r"-?\d+(?:\.\d+)?%?", text.replace(",", ""))


def _number_present(number: str, candidates: list[str], tolerance: float) -> bool:
    expected = float(number.rstrip("%"))
    for candidate in candidates:
        if candidate.endswith("%") != number.endswith("%"):
            continue
        actual = float(candidate.rstrip("%"))
        if abs(actual - expected) <= max(abs(expected) * tolerance, tolerance):
            return True
    return False


def _structured_conflict(
    claim: dict[str, Any], evidence: list[dict[str, Any]], tolerance: float
) -> str | None:
    text = str(claim["text"]).lower()
    payloads = [
        item.get("structured_payload", {}) for item in evidence if item["source_type"] == "sql_row"
    ]
    flattened = " ".join(json.dumps(payload, sort_keys=True).lower() for payload in payloads)
    status_conflicts = {
        "churned": ("active", "renewing", "at_risk", "at risk"),
        "approved": ("pending", "not_approved", "rejected"),
        "terminated": ("active", "renewing"),
    }
    for asserted, conflicts in status_conflicts.items():
        if asserted in text and any(conflict in flattened for conflict in conflicts):
            return f"Structured trace evidence records a status that conflicts with '{asserted}'."

    match = re.search(r"\b(?:is|was|equals?|of)\s+\$?(-?\d+(?:\.\d+)?%?)", text)
    if match and payloads:
        claimed = match.group(1)
        evidence_numbers = _numbers(flattened)
        if evidence_numbers and not _number_present(claimed, evidence_numbers, tolerance):
            return "Structured trace evidence contains a conflicting numeric value."
    return None


def _is_evidence_caveat(claim: dict[str, Any]) -> bool:
    lowered = str(claim["text"]).lower()
    return claim.get("assertion_mode") in {"caveated", "uncertain"} and any(
        phrase in lowered
        for phrase in (
            "no evidence",
            "do not see evidence",
            "not confirmed",
            "cannot determine",
            "not enough evidence",
            "does not show",
        )
    )


def _caveat_subject(text: str) -> str:
    lowered = text.lower()
    for phrase in (
        "no evidence that",
        "no evidence of",
        "do not see evidence that",
        "not confirmed that",
        "cannot determine whether",
        "does not show that",
    ):
        if phrase in lowered:
            return text[lowered.index(phrase) + len(phrase) :].strip(" .")
    return ""


def _normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _limit_evidence(evidence: list[dict[str, Any]], max_characters: int) -> list[dict[str, Any]]:
    limited: list[dict[str, Any]] = []
    used = 0
    for item in evidence:
        encoded = json.dumps(item, sort_keys=True)
        if limited and used + len(encoded) > max_characters:
            break
        limited.append(item)
        used += len(encoded)
    return limited
