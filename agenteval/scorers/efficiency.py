"""Efficiency and trace health scorers."""

from __future__ import annotations

from typing import Any

from agenteval.scorers.common import tool_events


def score_efficiency(task: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    max_tool_calls = task.get("expected_route", {}).get("max_tool_calls")
    calls = len(tool_events(run))
    if max_tool_calls is None:
        return {"score": 1.0, "tool_calls": calls, "failure_labels": []}
    max_calls = int(max_tool_calls)
    if calls <= max_calls:
        return {
            "score": 1.0,
            "tool_calls": calls,
            "max_tool_calls": max_calls,
            "failure_labels": [],
        }
    return {
        "score": round(max_calls / max(calls, 1), 3),
        "tool_calls": calls,
        "max_tool_calls": max_calls,
        "failure_labels": ["tool_loop"],
    }


def score_trace_errors(run: dict[str, Any]) -> dict[str, Any]:
    errors = [
        {"tool": event.get("tool"), "error": event.get("error")}
        for event in tool_events(run)
        if not event.get("success")
    ]
    return {
        "score": 1.0 if not errors else 0.0,
        "errors": errors,
        "failure_labels": ["tool_error"] if errors else [],
    }
