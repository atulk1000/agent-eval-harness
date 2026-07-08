"""Markdown report generation."""

from __future__ import annotations

from typing import Any


def render_report(summary: dict[str, Any], scores: list[dict[str, Any]]) -> str:
    lines = [
        f"# AgentEval Report: {summary.get('run_name', 'run')}",
        "",
        "## Overview",
        "",
        f"- Suite: `{summary.get('suite_id')}`",
        f"- Agent: `{summary.get('agent_name')}`",
        f"- Tasks: {summary.get('task_count')}",
        f"- Passed: {summary.get('passed')}",
        f"- Failed: {summary.get('failed')}",
        f"- Overall score: {summary.get('overall_score')}",
        f"- Unsupported claims: {summary.get('unsupported_claim_count')}",
        f"- High-severity unsupported claims: {summary.get('high_severity_claim_count')}",
        "",
        "## Dimension Averages",
        "",
    ]
    for dimension, value in summary.get("dimension_averages", {}).items():
        lines.append(f"- {dimension}: {value}")

    lines.extend(["", "## Task Results", ""])
    for score in scores:
        labels = ", ".join(score.get("failure_labels", [])) or "none"
        lines.extend(
            [
                f"### {score['task_id']}",
                "",
                f"- Type: `{score['task_type']}`",
                f"- Status: `{score['status']}`",
                f"- Overall score: {score['overall_score']}",
                f"- Actual route: {' -> '.join(score['tool_routing']['actual_route']) or 'none'}",
                f"- Failure labels: {labels}",
                f"- Unsupported claims: {len(score.get('unsupported_claims', []))}",
                "",
            ]
        )
        for claim in score.get("unsupported_claims", []):
            lines.extend(
                [
                    f"  - Claim: {claim['claim']}",
                    f"    - Verdict: {claim['verdict']}",
                    f"    - Severity: {claim['severity']}",
                    f"    - Reason: {claim['reason']}",
                ]
            )
        if score.get("unsupported_claims"):
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_comparison(comparison: dict[str, Any]) -> str:
    lines = [
        f"# AgentEval Comparison: {comparison['left']['run_name']} vs {comparison['right']['run_name']}",
        "",
        "## Summary",
        "",
        f"- Left overall score: {comparison['left']['overall_score']}",
        f"- Right overall score: {comparison['right']['overall_score']}",
        f"- Delta: {comparison['overall_score_delta']}",
        f"- Unsupported claim delta: {comparison['unsupported_claim_delta']}",
        "",
        "## Dimension Deltas",
        "",
    ]
    for dimension, delta in comparison.get("dimension_deltas", {}).items():
        lines.append(f"- {dimension}: {delta}")
    return "\n".join(lines).rstrip() + "\n"
