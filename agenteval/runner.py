"""Evaluation runner and artifact writer."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agents.registry import get_agent
from agenteval.benchmark import load_benchmark, tasks_by_id
from agenteval.data_loader import ensure_demo_data
from agenteval.reports.markdown import render_report
from agenteval.scorers import score_run
from agenteval.tools import Toolset
from agenteval.trace import TraceRecorder, read_jsonl, write_json, write_jsonl


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS_DIR = ROOT / "runs"


def run_suite(
    benchmark_path: str | Path,
    agent_name: str,
    *,
    output_dir: str | Path | None = None,
) -> Path:
    benchmark = load_benchmark(benchmark_path)
    db_path, docs_path = ensure_demo_data()
    agent_fn, model = get_agent(agent_name)
    run_dir = _make_run_dir(agent_name, output_dir)

    runs: list[dict[str, Any]] = []
    scores: list[dict[str, Any]] = []
    unsupported_claims: list[dict[str, Any]] = []
    for task in benchmark["tasks"]:
        recorder = TraceRecorder(task_id=task["id"], agent_name=agent_name, model=model)
        tools = Toolset(recorder, db_path=db_path, docs_path=docs_path)
        final_answer = agent_fn(task, tools)
        recorder.set_final_answer(final_answer)
        run = recorder.to_run()
        score = score_run(task, run)
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
) -> Path:
    benchmark = load_benchmark(benchmark_path)
    task_lookup = tasks_by_id(benchmark)
    runs = read_jsonl(trace_path)
    run_dir = _make_run_dir(agent_name, output_dir)
    scores = []
    unsupported_claims = []
    for run in runs:
        task_id = run.get("task_id")
        if task_id not in task_lookup:
            raise ValueError(f"Trace references unknown task_id: {task_id}")
        score = score_run(task_lookup[task_id], run)
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
            dimensions.setdefault(dimension, []).append(float(value))
    dimension_averages = {
        dimension: round(sum(values) / len(values), 3) for dimension, values in sorted(dimensions.items())
    }
    unsupported = [claim for score in scores for claim in score.get("unsupported_claims", [])]
    high = [claim for claim in unsupported if claim.get("severity") == "high"]
    passed = sum(1 for score in scores if score.get("status") == "pass")
    failed = len(scores) - passed
    overall = sum(score["overall_score"] for score in scores) / max(len(scores), 1)
    return {
        "suite_id": benchmark.get("suite_id"),
        "run_name": run_name,
        "agent_name": agent_name,
        "task_count": len(scores),
        "passed": passed,
        "failed": failed,
        "overall_score": round(overall, 3),
        "unsupported_claim_count": len(unsupported),
        "high_severity_claim_count": len(high),
        "dimension_averages": dimension_averages,
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
    (run_dir / "report.md").write_text(render_report(summary, scores), encoding="utf-8")


def _make_run_dir(agent_name: str, output_dir: str | Path | None = None) -> Path:
    if output_dir is not None:
        return Path(output_dir)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    safe_agent = re.sub(r"[^a-zA-Z0-9_-]+", "-", agent_name).strip("-")
    return DEFAULT_RUNS_DIR / f"{timestamp}-{safe_agent}"
