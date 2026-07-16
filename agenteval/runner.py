"""Evaluation runner and artifact writer."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agenteval.benchmark import load_benchmark, tasks_by_id
from agenteval.claim_eval.pipeline import ClaimEvaluationConfig
from agenteval.data_loader import ensure_demo_data
from agenteval.reports.markdown import render_report
from agenteval.schema import (
    TraceValidationError,
    ValidationIssue,
    ValidationReport,
    load_validated_trace_file,
)
from agenteval.scorers import score_run
from agenteval.tools import Toolset
from agenteval.trace import TraceRecorder, write_json, write_jsonl
from agents.registry import get_agent

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS_DIR = ROOT / "runs"


def run_suite(
    benchmark_path: str | Path,
    agent_name: str,
    *,
    output_dir: str | Path | None = None,
    claim_config: ClaimEvaluationConfig | None = None,
) -> Path:
    benchmark = load_benchmark(benchmark_path)
    db_path, docs_path = ensure_demo_data()
    agent_fn, model = get_agent(agent_name)
    run_dir = _make_run_dir(agent_name, output_dir)
    claim_config = claim_config or ClaimEvaluationConfig()
    claim_config.reset_runtime()

    runs: list[dict[str, Any]] = []
    scores: list[dict[str, Any]] = []
    unsupported_claims: list[dict[str, Any]] = []
    for task in benchmark["tasks"]:
        recorder = TraceRecorder(task_id=task["id"], agent_name=agent_name, model=model)
        tools = Toolset(recorder, db_path=db_path, docs_path=docs_path)
        final_answer = agent_fn(task, tools)
        recorder.set_final_answer(final_answer)
        run = recorder.to_run()
        score = score_run(task, run, claim_config)
        run["score"] = score
        runs.append(run)
        scores.append(score)
        for claim in score.get("unsupported_claims", []):
            unsupported_claims.append({"task_id": task["id"], **claim})

    summary = summarize_run(benchmark, agent_name, run_dir.name, scores)
    _write_artifacts(run_dir, runs, scores, summary, unsupported_claims)
    return run_dir


def score_trace_file(
    benchmark_path: str | Path,
    trace_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    agent_name: str = "external_trace",
    claim_config: ClaimEvaluationConfig | None = None,
) -> Path:
    benchmark = load_benchmark(benchmark_path)
    task_lookup = tasks_by_id(benchmark)
    runs = load_validated_trace_file(trace_path)
    run_dir = _make_run_dir(agent_name, output_dir)
    claim_config = claim_config or ClaimEvaluationConfig()
    claim_config.reset_runtime()
    scores = []
    unsupported_claims = []
    unknown_task_issues = []
    for line_number, run in enumerate(runs, start=1):
        task_id = run.get("task_id")
        if task_id not in task_lookup:
            unknown_task_issues.append(
                ValidationIssue(
                    path="$.task_id",
                    message=f"unknown benchmark task_id: {task_id}",
                    code="unknown_task_id",
                    line=line_number,
                )
            )
    if unknown_task_issues:
        raise TraceValidationError(ValidationReport(rows=runs, errors=unknown_task_issues))

    for run in runs:
        task_id = run["task_id"]
        score = score_run(task_lookup[task_id], run, claim_config)
        run["score"] = score
        scores.append(score)
        for claim in score.get("unsupported_claims", []):
            unsupported_claims.append({"task_id": task_id, **claim})
    summary = summarize_run(benchmark, agent_name, run_dir.name, scores)
    _write_artifacts(run_dir, runs, scores, summary, unsupported_claims)
    return run_dir


def summarize_run(
    benchmark: dict[str, Any],
    agent_name: str,
    run_name: str,
    scores: list[dict[str, Any]],
) -> dict[str, Any]:
    dimensions: dict[str, list[float]] = {}
    for score in scores:
        for dimension, value in score.get("dimension_scores", {}).items():
            if value is None:
                continue
            dimensions.setdefault(dimension, []).append(float(value))
    dimension_averages = {
        dimension: round(sum(values) / len(values), 3)
        for dimension, values in sorted(dimensions.items())
    }
    unsupported = [claim for score in scores for claim in score.get("unsupported_claims", [])]
    high = [claim for claim in unsupported if claim.get("severity") == "high"]
    passed = sum(1 for score in scores if score.get("status") == "pass")
    failed = sum(1 for score in scores if score.get("status") == "fail")
    needs_review = sum(1 for score in scores if score.get("status") == "needs_review")
    overall = sum(score["overall_score"] for score in scores) / max(len(scores), 1)
    claim_metrics = _claim_metrics(scores)
    return {
        "suite_id": benchmark.get("suite_id"),
        "run_name": run_name,
        "agent_name": agent_name,
        "task_count": len(scores),
        "passed": passed,
        "failed": failed,
        "needs_review": needs_review,
        "overall_score": round(overall, 3),
        "unsupported_claim_count": len(unsupported),
        "high_severity_claim_count": len(high),
        "dimension_averages": dimension_averages,
        "claim_count": claim_metrics["claim_count"],
        "claim_verdict_counts": claim_metrics["verdict_counts"],
        "claim_needs_review_count": claim_metrics["needs_review_count"],
    }


def _write_artifacts(
    run_dir: Path,
    runs: list[dict[str, Any]],
    scores: list[dict[str, Any]],
    summary: dict[str, Any],
    unsupported_claims: list[dict[str, Any]],
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(run_dir / "traces.jsonl", runs)
    write_json(run_dir / "scores.json", scores)
    write_json(run_dir / "summary.json", summary)
    write_json(run_dir / "unsupported_claims.json", unsupported_claims)
    claim_artifacts = _claim_artifacts(scores)
    write_jsonl(run_dir / "claims.jsonl", claim_artifacts["claims"])
    write_jsonl(run_dir / "evidence.jsonl", claim_artifacts["evidence"])
    write_jsonl(run_dir / "claim_verdicts.jsonl", claim_artifacts["verdicts"])
    write_jsonl(run_dir / "judge_calls.jsonl", claim_artifacts["judge_calls"])
    write_jsonl(run_dir / "annotations.jsonl", [])
    write_json(run_dir / "claim_metrics.json", _claim_metrics(scores))
    (run_dir / "report.md").write_text(render_report(summary, scores), encoding="utf-8")


def _claim_artifacts(scores: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    artifacts: dict[str, list[dict[str, Any]]] = {
        "claims": [],
        "evidence": [],
        "verdicts": [],
        "judge_calls": [],
    }
    for score in scores:
        evaluation = score.get("claim_evaluation", {})
        for name in artifacts:
            artifacts[name].extend(evaluation.get(name, []))
    return artifacts


def _claim_metrics(scores: list[dict[str, Any]]) -> dict[str, Any]:
    artifacts = _claim_artifacts(scores)
    verdict_counts: dict[str, int] = {}
    for verdict in artifacts["verdicts"]:
        label = verdict["verdict"]
        verdict_counts[label] = verdict_counts.get(label, 0) + 1
    metrics = [score.get("claim_evaluation", {}).get("metrics", {}) for score in scores]
    return {
        "schema_version": "1.0",
        "claim_count": len(artifacts["claims"]),
        "evidence_count": len(artifacts["evidence"]),
        "judge_call_count": len(artifacts["judge_calls"]),
        "verdict_counts": dict(sorted(verdict_counts.items())),
        "needs_review_count": sum(item.get("needs_review_count", 0) for item in metrics),
        "hard_gate_failure_count": sum(len(item.get("hard_gate_failures", [])) for item in metrics),
    }


def _make_run_dir(agent_name: str, output_dir: str | Path | None = None) -> Path:
    if output_dir is not None:
        return Path(output_dir)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    safe_agent = re.sub(r"[^a-zA-Z0-9_-]+", "-", agent_name).strip("-")
    return DEFAULT_RUNS_DIR / f"{timestamp}-{safe_agent}"
