"""Versioned trace validation for built-in and external agent runs."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

CURRENT_SCHEMA_VERSION = "1.0"
SUPPORTED_SCHEMA_VERSIONS = {CURRENT_SCHEMA_VERSION}


@dataclass(frozen=True)
class ValidationIssue:
    """One actionable trace validation issue."""

    path: str
    message: str
    code: str
    line: int | None = None

    def format(self) -> str:
        location = f"line {self.line}, " if self.line is not None else ""
        return f"{location}{self.path}: {self.message} [{self.code}]"


@dataclass
class ValidationReport:
    """Normalized rows plus all errors and compatibility warnings."""

    rows: list[dict[str, Any]] = field(default_factory=list)
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors


class TraceValidationError(ValueError):
    """Raised when a trace file does not satisfy the public contract."""

    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        details = "\n".join(f"- {issue.format()}" for issue in report.errors)
        super().__init__(f"Trace validation failed with {len(report.errors)} error(s):\n{details}")


def validate_trace_file(path: str | Path, *, allow_legacy: bool = True) -> ValidationReport:
    """Parse and validate every JSONL row, collecting all issues."""

    trace_path = Path(path)
    report = ValidationReport()
    seen_task_ids: dict[str, int] = {}

    for line_number, line in enumerate(
        trace_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            report.errors.append(
                ValidationIssue(
                    path="$",
                    message=f"invalid JSON: {exc.msg}",
                    code="invalid_json",
                    line=line_number,
                )
            )
            continue
        if not isinstance(payload, dict):
            report.errors.append(
                ValidationIssue(
                    path="$",
                    message="run must be a JSON object",
                    code="invalid_run_type",
                    line=line_number,
                )
            )
            continue

        normalized, warnings = normalize_run(payload, allow_legacy=allow_legacy, line=line_number)
        report.warnings.extend(warnings)
        report.errors.extend(validate_run(normalized, line=line_number))
        report.rows.append(normalized)

        task_id = normalized.get("task_id")
        if isinstance(task_id, str) and task_id:
            if task_id in seen_task_ids:
                report.errors.append(
                    ValidationIssue(
                        path="$.task_id",
                        message=f"duplicate task_id; first appeared on line {seen_task_ids[task_id]}",
                        code="duplicate_task_id",
                        line=line_number,
                    )
                )
            else:
                seen_task_ids[task_id] = line_number

    if not report.rows and not report.errors:
        report.errors.append(
            ValidationIssue(
                path="$", message="trace file contains no runs", code="empty_trace_file"
            )
        )
    return report


def load_validated_trace_file(
    path: str | Path, *, allow_legacy: bool = True
) -> list[dict[str, Any]]:
    """Return normalized rows or raise one error containing every issue."""

    report = validate_trace_file(path, allow_legacy=allow_legacy)
    if not report.valid:
        raise TraceValidationError(report)
    return report.rows


def normalize_run(
    run: dict[str, Any], *, allow_legacy: bool = True, line: int | None = None
) -> tuple[dict[str, Any], list[ValidationIssue]]:
    """Copy a run and add compatibility fields without mutating input."""

    normalized = copy.deepcopy(run)
    warnings: list[ValidationIssue] = []
    if "schema_version" not in normalized and allow_legacy:
        normalized["schema_version"] = CURRENT_SCHEMA_VERSION
        warnings.append(
            ValidationIssue(
                path="$.schema_version",
                message="legacy run normalized to schema version 1.0",
                code="legacy_schema_version",
                line=line,
            )
        )
    return normalized, warnings


def validate_run(run: dict[str, Any], *, line: int | None = None) -> list[ValidationIssue]:
    """Validate one normalized run object."""

    errors: list[ValidationIssue] = []
    required_strings = (
        "schema_version",
        "run_id",
        "task_id",
        "agent_name",
        "model",
        "started_at",
        "completed_at",
        "final_answer",
    )
    for field_name in required_strings:
        value = run.get(field_name)
        if not isinstance(value, str):
            errors.append(_issue(field_name, "must be a string", "invalid_field_type", line))
        elif field_name != "final_answer" and not value.strip():
            errors.append(_issue(field_name, "must not be empty", "empty_required_field", line))

    version = run.get("schema_version")
    if isinstance(version, str) and version not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append(
            _issue(
                "schema_version",
                f"unsupported version {version!r}; supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)}",
                "unsupported_schema_version",
                line,
            )
        )

    for field_name in ("started_at", "completed_at"):
        value = run.get(field_name)
        if isinstance(value, str) and value and not _is_iso_datetime(value):
            errors.append(
                _issue(field_name, "must be an ISO-8601 datetime", "invalid_datetime", line)
            )

    metadata = run.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        errors.append(_issue("metadata", "must be an object", "invalid_field_type", line))

    trace = run.get("trace")
    if not isinstance(trace, list):
        errors.append(_issue("trace", "must be a list", "invalid_field_type", line))
        return errors

    previous_step = 0
    seen_steps: set[int] = set()
    for index, event in enumerate(trace):
        event_path = f"trace[{index}]"
        if not isinstance(event, dict):
            errors.append(_issue_path(event_path, "must be an object", "invalid_event_type", line))
            continue
        errors.extend(_validate_event(event, event_path, line))
        step = event.get("step")
        if _is_int(step):
            if step in seen_steps:
                errors.append(
                    _issue_path(f"{event_path}.step", "must be unique", "duplicate_step", line)
                )
            if step <= previous_step:
                errors.append(
                    _issue_path(
                        f"{event_path}.step",
                        "must be strictly increasing",
                        "non_increasing_step",
                        line,
                    )
                )
            seen_steps.add(step)
            previous_step = max(previous_step, step)
    return errors


def _validate_event(event: dict[str, Any], path: str, line: int | None) -> list[ValidationIssue]:
    errors: list[ValidationIssue] = []
    step = event.get("step")
    if not _is_int(step) or step <= 0:
        errors.append(
            _issue_path(f"{path}.step", "must be a positive integer", "invalid_step", line)
        )
    if event.get("type") != "tool_call":
        errors.append(
            _issue_path(f"{path}.type", "must equal 'tool_call'", "invalid_event_kind", line)
        )
    tool = event.get("tool")
    if not isinstance(tool, str) or not tool.strip():
        errors.append(
            _issue_path(f"{path}.tool", "must be a non-empty string", "invalid_tool", line)
        )
    for field_name in ("input", "output"):
        if not isinstance(event.get(field_name), dict):
            errors.append(
                _issue_path(f"{path}.{field_name}", "must be an object", "invalid_field_type", line)
            )
    success = event.get("success")
    if not isinstance(success, bool):
        errors.append(
            _issue_path(f"{path}.success", "must be a boolean", "invalid_field_type", line)
        )
    error = event.get("error")
    if error is not None and not isinstance(error, str):
        errors.append(
            _issue_path(f"{path}.error", "must be null or a string", "invalid_field_type", line)
        )
    if success is False and (not isinstance(error, str) or not error.strip()):
        errors.append(
            _issue_path(
                f"{path}.error",
                "must describe the failure when success is false",
                "missing_event_error",
                line,
            )
        )
    latency = event.get("latency_ms")
    if not _is_int(latency) or latency < 0:
        errors.append(
            _issue_path(
                f"{path}.latency_ms",
                "must be a non-negative integer",
                "invalid_latency",
                line,
            )
        )

    output = event.get("output")
    if isinstance(output, dict) and tool == "sql_query" and "rows" in output:
        errors.extend(_validate_object_list(output["rows"], f"{path}.output.rows", line))
    if isinstance(output, dict) and tool == "rag_search" and "documents" in output:
        documents = output["documents"]
        errors.extend(_validate_object_list(documents, f"{path}.output.documents", line))
        if isinstance(documents, list):
            for index, document in enumerate(documents):
                if not isinstance(document, dict):
                    continue
                document_path = f"{path}.output.documents[{index}]"
                if not isinstance(document.get("doc_id"), str) or not document["doc_id"].strip():
                    errors.append(
                        _issue_path(
                            f"{document_path}.doc_id",
                            "must be a non-empty string",
                            "invalid_document_id",
                            line,
                        )
                    )
                if not isinstance(document.get("text"), str):
                    errors.append(
                        _issue_path(
                            f"{document_path}.text",
                            "must be a string",
                            "invalid_document_text",
                            line,
                        )
                    )
    return errors


def _validate_object_list(value: Any, path: str, line: int | None) -> list[ValidationIssue]:
    if not isinstance(value, list):
        return [_issue_path(path, "must be a list", "invalid_field_type", line)]
    return [
        _issue_path(f"{path}[{index}]", "must be an object", "invalid_item_type", line)
        for index, item in enumerate(value)
        if not isinstance(item, dict)
    ]


def _is_iso_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _issue(field_name: str, message: str, code: str, line: int | None) -> ValidationIssue:
    return _issue_path(f"$.{field_name}", message, code, line)


def _issue_path(path: str, message: str, code: str, line: int | None) -> ValidationIssue:
    return ValidationIssue(path=path, message=message, code=code, line=line)
