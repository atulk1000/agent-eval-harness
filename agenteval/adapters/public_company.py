"""Public Company Research Assistant response and capture adapter."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from agenteval.benchmark import load_benchmark, tasks_by_id
from agenteval.schema import CURRENT_SCHEMA_VERSION, TraceValidationError, validate_trace_file
from agenteval.trace import utc_now, write_jsonl

TABLE_PATTERN = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.IGNORECASE)


class PCAAdapterError(ValueError):
    """Raised when PCA output lacks the evidence required for a truthful trace."""


def adapt_pca_response_file(
    responses_path: str | Path,
    benchmark_path: str | Path,
    output_path: str | Path,
) -> int:
    """Convert raw PCA response JSONL into validated AgentEval trace JSONL."""

    task_lookup = tasks_by_id(load_benchmark(benchmark_path))
    rows = _read_raw_rows(responses_path)
    traces: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_number, row in enumerate(rows, start=1):
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise PCAAdapterError(f"line {line_number}: task_id must be a non-empty string")
        if task_id not in task_lookup:
            raise PCAAdapterError(f"line {line_number}: unknown benchmark task_id: {task_id}")
        if task_id in seen:
            raise PCAAdapterError(f"line {line_number}: duplicate task_id: {task_id}")
        seen.add(task_id)
        response = row.get("response")
        if not isinstance(response, dict):
            raise PCAAdapterError(
                f"line {line_number}: response must contain the raw PCA response object; "
                "summary-only evaluation results are not sufficient"
            )
        traces.append(adapt_pca_response(task_id, response, capture=row))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_path, traces)
    report = validate_trace_file(output_path, allow_legacy=False)
    if not report.valid:
        raise TraceValidationError(report)
    return len(traces)


def adapt_pca_response(
    task_id: str,
    response: dict[str, Any],
    *,
    capture: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map one evidence-bearing PCA response without fabricating tool events."""

    if "answer" not in response:
        raise PCAAdapterError(
            f"{task_id}: response has no answer; pass the raw answer_question response, not an eval summary"
        )
    if "structured_evidence" not in response and "retrieved_evidence" not in response:
        raise PCAAdapterError(
            f"{task_id}: response has no evidence fields; summary booleans cannot be adapted"
        )

    capture = capture or {}
    captured_at = _string_or(capture.get("captured_at"), utc_now())
    events: list[dict[str, Any]] = []
    structured = response.get("structured_evidence")
    if structured is not None:
        if not isinstance(structured, dict):
            raise PCAAdapterError(f"{task_id}: structured_evidence must be an object or null")
        query = structured.get("sql") or ""
        rows = structured.get("rows") or []
        if not isinstance(query, str):
            raise PCAAdapterError(f"{task_id}: structured_evidence.sql must be a string")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise PCAAdapterError(f"{task_id}: structured_evidence.rows must be a list of objects")
        if query or rows:
            events.append(
                {
                    "step": len(events) + 1,
                    "type": "tool_call",
                    "tool": "sql_query",
                    "input": {"query": query},
                    "output": {
                        "rows": rows,
                        "tables_used": sorted(set(TABLE_PATTERN.findall(query))),
                    },
                    "success": True,
                    "error": None,
                    "latency_ms": _non_negative_int(structured.get("latency_ms")),
                }
            )

    retrieved = response.get("retrieved_evidence")
    if retrieved is not None:
        if not isinstance(retrieved, list) or any(not isinstance(item, dict) for item in retrieved):
            raise PCAAdapterError(
                f"{task_id}: retrieved_evidence must be a list of objects or null"
            )
        if retrieved:
            documents = [
                _map_document(item, index) for index, item in enumerate(retrieved, start=1)
            ]
            events.append(
                {
                    "step": len(events) + 1,
                    "type": "tool_call",
                    "tool": "rag_search",
                    "input": {"query": _string_or(capture.get("prompt"), task_id)},
                    "output": {"documents": documents},
                    "success": True,
                    "error": None,
                    "latency_ms": 0,
                }
            )

    metadata = {
        "adapter": "public_company_research_assistant",
        "route": response.get("route"),
        "status": response.get("status"),
        "source_repository": "public-company-research-assistant",
        "source_revision": capture.get("source_revision"),
        "fixture_kind": capture.get("fixture_kind"),
        "agent_trace": response.get("agent_trace"),
        "research_plan": response.get("research_plan") or response.get("planning"),
    }
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "run_id": _string_or(capture.get("run_id"), f"pca_{task_id}"),
        "task_id": task_id,
        "agent_name": "public_company_research_assistant",
        "model": _string_or(capture.get("model"), "pca-current"),
        "started_at": _string_or(capture.get("started_at"), captured_at),
        "completed_at": _string_or(capture.get("completed_at"), captured_at),
        "final_answer": str(response.get("answer") or ""),
        "trace": events,
        "metadata": {key: value for key, value in metadata.items() if value is not None},
    }


def capture_pca_responses(
    pca_repo: str | Path,
    benchmark_path: str | Path,
    output_path: str | Path,
    *,
    pca_python: str | Path | None = None,
) -> int:
    """Run the standalone capture worker in PCA's Python environment."""

    benchmark = load_benchmark(benchmark_path)
    task_count = len(benchmark["tasks"])
    worker = Path(__file__).with_name("pca_capture_worker.py")
    command = [
        str(pca_python or sys.executable),
        str(worker),
        "--pca-repo",
        str(Path(pca_repo).resolve()),
        "--benchmark",
        str(Path(benchmark_path).resolve()),
        "--out",
        str(Path(output_path).resolve()),
    ]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown capture error"
        raise PCAAdapterError(f"PCA capture failed: {detail}")
    return task_count


def _read_raw_rows(path: str | Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PCAAdapterError(f"line {line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise PCAAdapterError(f"line {line_number}: raw response row must be an object")
        rows.append(value)
    if not rows:
        raise PCAAdapterError("raw response file is empty")
    return rows


def _map_document(item: dict[str, Any], index: int) -> dict[str, Any]:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    doc_id = item.get("source") or metadata.get("chunk_id") or metadata.get("document_id")
    if not doc_id:
        parts = [metadata.get("ticker"), metadata.get("doc_type"), metadata.get("doc_date"), index]
        doc_id = "_".join(_slug(str(part)) for part in parts if part is not None)
    text = item.get("text", item.get("chunk_text", ""))
    return {
        "doc_id": str(doc_id),
        "title": str(item.get("title") or metadata.get("title") or doc_id),
        "doc_type": str(metadata.get("doc_type") or "filing"),
        "score": _float_or_zero(item.get("score")),
        "text": str(text or ""),
        "metadata": metadata,
    }


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower()


def _string_or(value: Any, default: str) -> str:
    return value if isinstance(value, str) and value else default


def _non_negative_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _float_or_zero(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0
