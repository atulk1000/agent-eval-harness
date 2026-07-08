"""Trace capture and serialization."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> str:
    """Return an ISO timestamp in UTC."""

    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass
class TraceRecorder:
    """Collect observable agent events for one benchmark task."""

    task_id: str
    agent_name: str
    model: str
    run_id: str = field(default_factory=lambda: f"run_{uuid.uuid4().hex[:12]}")
    started_at: str = field(default_factory=utc_now)
    trace: list[dict[str, Any]] = field(default_factory=list)
    final_answer: str = ""
    completed_at: str | None = None

    def record_tool(
        self,
        tool: str,
        tool_input: dict[str, Any],
        output: dict[str, Any],
        *,
        success: bool = True,
        error: str | None = None,
        latency_ms: int = 0,
    ) -> dict[str, Any]:
        """Append a tool event and return the output."""

        event = {
            "step": len(self.trace) + 1,
            "type": "tool_call",
            "tool": tool,
            "input": tool_input,
            "output": output,
            "success": success,
            "error": error,
            "latency_ms": latency_ms,
        }
        self.trace.append(event)
        return output

    def set_final_answer(self, answer: str) -> None:
        self.final_answer = answer
        self.completed_at = utc_now()

    def to_run(self) -> dict[str, Any]:
        """Return a JSON-serializable agent run."""

        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "agent_name": self.agent_name,
            "model": self.model,
            "started_at": self.started_at,
            "completed_at": self.completed_at or utc_now(),
            "final_answer": self.final_answer,
            "trace": self.trace,
        }


def timed_call(fn):
    """Run a callable and return (result, latency_ms)."""

    started = time.perf_counter()
    result = fn()
    latency_ms = int((time.perf_counter() - started) * 1000)
    return result, latency_ms


def write_json(path: str | Path, payload: Any) -> None:
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    content = "\n".join(json.dumps(row, sort_keys=True) for row in rows)
    Path(path).write_text(content + ("\n" if content else ""), encoding="utf-8")


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows
