"""Versioned record contracts and deterministic identifiers for claim evaluation."""

from __future__ import annotations

import hashlib
import re
from typing import Any

SCHEMA_VERSION = "1.0"
CLAIM_TYPES = {
    "numeric",
    "entity_fact",
    "business_status",
    "policy_or_requirement",
    "causal",
    "comparative",
    "source_attribution",
    "descriptive",
    "other",
}
ASSERTION_MODES = {"asserted", "caveated", "uncertain"}
SOURCE_REQUIREMENTS = {"sql", "rag", "hybrid", "any"}
EVIDENCE_TYPES = {"sql_row", "document_chunk", "opened_document", "tool_error", "empty_result"}
VERDICTS = {
    "supported",
    "partially_supported",
    "unsupported",
    "contradicted",
    "not_enough_evidence",
}
RISK_LEVELS = {"low", "medium", "high"}
SEVERITIES = {"none", "low", "medium", "high"}
JUDGE_PATHS = {"deterministic", "semantic", "deterministic_precedence", "unresolved"}
JUDGE_STATUSES = {"success", "invalid_output", "timeout", "budget_exhausted", "error"}
DATASET_SPLITS = {"development", "calibration", "held_out", "run"}
REVIEW_STAGES = {"primary", "independent", "adjudicator"}


class RecordValidationError(ValueError):
    """Raised when a claim-evaluation artifact violates its contract."""


def stable_id(prefix: str, *parts: Any, length: int = 12) -> str:
    normalized = "\x1f".join(_normalize_id_part(part) for part in parts)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}_{digest}"


def claim_id(task_id: str, ordinal: int, text: str) -> str:
    safe_task = re.sub(r"[^a-zA-Z0-9]+", "_", task_id).strip("_")[:32] or "task"
    digest = stable_id("", task_id, ordinal, text, length=8).lstrip("_")
    return f"claim_{safe_task}_{ordinal:02d}_{digest}"


def validate_claim(record: dict[str, Any]) -> dict[str, Any]:
    _require(
        record,
        "schema_version",
        "claim_id",
        "run_id",
        "task_id",
        "ordinal",
        "text",
        "source_text",
        "source_span",
        "extractor",
    )
    _version(record)
    _non_empty(record, "claim_id", "run_id", "task_id", "text")
    if not isinstance(record["ordinal"], int) or record["ordinal"] < 1:
        raise RecordValidationError("claim ordinal must be a positive integer")
    _choice(record, "claim_type", CLAIM_TYPES)
    _choice(record, "assertion_mode", ASSERTION_MODES)
    _choice(record, "source_requirement", SOURCE_REQUIREMENTS)
    span = record.get("source_span")
    if (
        not isinstance(span, dict)
        or not isinstance(span.get("start"), int)
        or not isinstance(span.get("end"), int)
    ):
        raise RecordValidationError("claim source_span must contain integer start and end")
    if span["start"] < 0 or span["end"] < span["start"]:
        raise RecordValidationError("claim source_span is invalid")
    return record


def validate_evidence(record: dict[str, Any]) -> dict[str, Any]:
    _require(
        record,
        "schema_version",
        "evidence_id",
        "run_id",
        "task_id",
        "source_type",
        "tool",
        "tool_step",
        "content",
        "structured_payload",
        "provenance",
    )
    _version(record)
    _non_empty(record, "evidence_id", "run_id", "task_id")
    _choice(record, "source_type", EVIDENCE_TYPES)
    if not isinstance(record["content"], str):
        raise RecordValidationError("evidence content must be a string")
    if not isinstance(record.get("tool_step"), int) or record["tool_step"] < 1:
        raise RecordValidationError("evidence tool_step must be a positive integer")
    provenance = record.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("trace_run_id") != record["run_id"]:
        raise RecordValidationError("evidence provenance must link to its trace run")
    return record


def validate_verdict(record: dict[str, Any]) -> dict[str, Any]:
    _require(
        record,
        "schema_version",
        "claim_id",
        "run_id",
        "task_id",
        "verdict",
        "confidence",
        "reason",
        "evidence_refs",
        "evidence_considered",
        "unsupported_parts",
        "judge_path",
        "risk_level",
        "severity",
        "severity_reason",
        "requires_review",
    )
    _version(record)
    _choice(record, "verdict", VERDICTS)
    _choice(record, "risk_level", RISK_LEVELS)
    _choice(record, "severity", SEVERITIES)
    _choice(record, "judge_path", JUDGE_PATHS)
    confidence = record["confidence"]
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise RecordValidationError("verdict confidence must be between 0 and 1")
    if not isinstance(record["reason"], str) or not record["reason"].strip():
        raise RecordValidationError("verdict reason must be non-empty")
    if not isinstance(record["evidence_refs"], list) or not all(
        isinstance(item, str) for item in record["evidence_refs"]
    ):
        raise RecordValidationError("verdict evidence_refs must be a list of strings")
    return record


def validate_judge_call(record: dict[str, Any]) -> dict[str, Any]:
    _require(
        record,
        "schema_version",
        "judge_call_id",
        "claim_id",
        "provider",
        "model",
        "prompt_version",
        "temperature",
        "cache_key",
        "cache_hit",
        "status",
        "redacted",
        "error",
    )
    _version(record)
    _choice(record, "status", JUDGE_STATUSES)
    for field in ("latency_ms", "input_tokens", "output_tokens"):
        if not isinstance(record.get(field), int) or record[field] < 0:
            raise RecordValidationError(f"judge call {field} must be a non-negative integer")
    if not isinstance(record.get("estimated_cost"), (int, float)) or record["estimated_cost"] < 0:
        raise RecordValidationError("judge call estimated_cost must be non-negative")
    return record


def validate_annotation(record: dict[str, Any]) -> dict[str, Any]:
    _require(
        record,
        "schema_version",
        "annotation_id",
        "claim_id",
        "reviewer_id",
        "verdict",
        "severity",
        "evidence_refs",
        "rationale",
        "dataset_split",
        "review_stage",
        "created_at",
    )
    _version(record)
    _choice(record, "verdict", VERDICTS)
    _choice(record, "severity", SEVERITIES)
    _choice(record, "dataset_split", DATASET_SPLITS)
    _choice(record, "review_stage", REVIEW_STAGES)
    _non_empty(record, "annotation_id", "claim_id", "reviewer_id", "rationale", "created_at")
    if not isinstance(record["evidence_refs"], list):
        raise RecordValidationError("annotation evidence_refs must be a list")
    return record


def _normalize_id_part(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _require(record: dict[str, Any], *fields: str) -> None:
    missing = [field for field in fields if field not in record]
    if missing:
        raise RecordValidationError(f"missing required field(s): {', '.join(missing)}")


def _version(record: dict[str, Any]) -> None:
    if record.get("schema_version") != SCHEMA_VERSION:
        raise RecordValidationError(
            f"unsupported record schema version: {record.get('schema_version')}"
        )


def _non_empty(record: dict[str, Any], *fields: str) -> None:
    for field in fields:
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise RecordValidationError(f"{field} must be a non-empty string")


def _choice(record: dict[str, Any], field: str, choices: set[str]) -> None:
    if record.get(field) not in choices:
        raise RecordValidationError(f"{field} must be one of: {', '.join(sorted(choices))}")
