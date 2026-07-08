"""Benchmark loading and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class BenchmarkError(ValueError):
    """Raised when a benchmark file is invalid."""


def load_benchmark(path: str | Path) -> dict[str, Any]:
    """Load a benchmark suite.

    The bundled benchmark is JSON-compatible YAML so the project can run with
    only the Python standard library. If JSON parsing fails and PyYAML is
    installed, this function also accepts ordinary YAML.
    """

    benchmark_path = Path(path)
    text = benchmark_path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except ModuleNotFoundError as exc:
            raise BenchmarkError(
                f"{benchmark_path} is not JSON-compatible YAML and PyYAML is not installed."
            ) from exc
        payload = yaml.safe_load(text)

    if not isinstance(payload, dict):
        raise BenchmarkError("Benchmark root must be an object.")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise BenchmarkError("Benchmark must include a non-empty 'tasks' list.")

    seen: set[str] = set()
    for task in tasks:
        if not isinstance(task, dict):
            raise BenchmarkError("Each task must be an object.")
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id:
            raise BenchmarkError("Each task must include a string 'id'.")
        if task_id in seen:
            raise BenchmarkError(f"Duplicate task id: {task_id}")
        seen.add(task_id)
        if task.get("task_type") not in {"sql_only", "rag_only", "hybrid_sql_rag"}:
            raise BenchmarkError(f"{task_id} has invalid task_type.")
        if not isinstance(task.get("prompt"), str) or not task["prompt"].strip():
            raise BenchmarkError(f"{task_id} must include a prompt.")
        if "expected_route" not in task:
            raise BenchmarkError(f"{task_id} must include expected_route.")
    return payload


def tasks_by_id(benchmark: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return benchmark tasks keyed by id."""

    return {task["id"]: task for task in benchmark["tasks"]}
