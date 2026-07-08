"""Tool routing scorer."""

from __future__ import annotations

from typing import Any

from agenteval.scorers.common import actual_route, clamp


def score_tool_routing(task: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    expected = task.get("expected_route", {})
    required = set(expected.get("required_tools", []))
    forbidden = set(expected.get("forbidden_tools", []))
    max_tool_calls = expected.get("max_tool_calls")
    route = actual_route(run)
    route_set = set(route)
    labels: list[str] = []

    missing = sorted(required - route_set)
    forbidden_used = sorted(forbidden & route_set)
    if missing:
        labels.append("missing_required_tool")
    if forbidden_used:
        labels.append("forbidden_tool_used")
    if run.get("final_answer") and missing and len(route) <= 1:
        labels.append("premature_final_answer")
    if max_tool_calls is not None and len(route) > int(max_tool_calls):
        labels.append("tool_loop")

    required_score = 1.0 if not required else (len(required & route_set) / len(required))
    forbidden_score = 1.0 if not forbidden_used else 0.0
    order_score = _order_score(route, list(expected.get("required_tools", [])))
    premature_score = 0.0 if "premature_final_answer" in labels else 1.0
    budget_score = 1.0
    if max_tool_calls is not None and len(route) > int(max_tool_calls):
        budget_score = max(0.0, int(max_tool_calls) / max(len(route), 1))

    score = clamp(
        required_score * 0.50
        + forbidden_score * 0.20
        + order_score * 0.15
        + premature_score * 0.10
        + budget_score * 0.05
    )
    return {
        "score": round(score, 3),
        "actual_route": route,
        "missing_tools": missing,
        "forbidden_tools_used": forbidden_used,
        "failure_labels": labels,
    }


def _order_score(route: list[str], required_in_order: list[str]) -> float:
    if not required_in_order:
        return 1.0
    position = -1
    matched = 0
    for tool in required_in_order:
        try:
            next_position = route.index(tool, position + 1)
        except ValueError:
            continue
        matched += 1
        position = next_position
    return matched / len(required_in_order)
