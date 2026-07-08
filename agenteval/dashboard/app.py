"""Streamlit dashboard for AgentEval run artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = ROOT / "runs"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_dirs() -> list[Path]:
    if not RUNS_DIR.exists():
        return []
    return sorted(
        [path for path in RUNS_DIR.iterdir() if path.is_dir() and (path / "summary.json").exists()],
        reverse=True,
    )


def _load_run(run_dir: Path) -> dict[str, Any]:
    return {
        "dir": run_dir,
        "summary": _load_json(run_dir / "summary.json"),
        "scores": _load_json(run_dir / "scores.json"),
        "unsupported_claims": _load_json(run_dir / "unsupported_claims.json"),
        "traces": [
            json.loads(line)
            for line in (run_dir / "traces.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ],
    }


def main() -> None:
    try:
        import streamlit as st
    except ModuleNotFoundError:
        print("Streamlit is not installed. Install with: pip install -e .[dashboard]")
        return

    st.set_page_config(page_title="AgentEval Harness", layout="wide")
    st.title("AgentEval Harness")
    st.caption("Trace-based evaluation for hybrid SQL + RAG agents")

    runs = _run_dirs()
    if not runs:
        st.info("No run artifacts found. Run `python -m agenteval.cli run benchmarks/customer_risk.yaml --agent improved_agent` first.")
        return

    selected = st.sidebar.selectbox("Run", runs, format_func=lambda path: path.name)
    run = _load_run(selected)
    summary = run["summary"]

    tab_overview, tab_tasks, tab_trace, tab_claims, tab_compare = st.tabs(
        ["Overview", "Task Results", "Trace & Evidence", "Unsupported Claims", "Compare Runs"]
    )

    with tab_overview:
        cols = st.columns(5)
        cols[0].metric("Overall", summary["overall_score"])
        cols[1].metric("Passed", summary["passed"])
        cols[2].metric("Failed", summary["failed"])
        cols[3].metric("Unsupported Claims", summary["unsupported_claim_count"])
        cols[4].metric("High Severity", summary["high_severity_claim_count"])
        st.subheader("Dimension Averages")
        st.json(summary["dimension_averages"])

    with tab_tasks:
        rows = []
        for score in run["scores"]:
            rows.append(
                {
                    "task_id": score["task_id"],
                    "task_type": score["task_type"],
                    "status": score["status"],
                    "overall_score": score["overall_score"],
                    "actual_route": " -> ".join(score["tool_routing"]["actual_route"]),
                    "failure_labels": ", ".join(score["failure_labels"]),
                    "unsupported_claims": len(score["unsupported_claims"]),
                }
            )
        st.dataframe(rows, use_container_width=True)

    with tab_trace:
        task_ids = [score["task_id"] for score in run["scores"]]
        selected_task = st.selectbox("Task", task_ids)
        score = next(item for item in run["scores"] if item["task_id"] == selected_task)
        trace = next(item for item in run["traces"] if item["task_id"] == selected_task)
        st.subheader(selected_task)
        st.write("Final answer")
        st.info(trace["final_answer"])
        st.write("Score breakdown")
        st.json(score["dimension_scores"])
        st.write("Tool trace")
        for event in trace["trace"]:
            with st.expander(f"{event['step']}. {event['tool']}"):
                st.write("Input")
                st.json(event["input"])
                st.write("Output")
                st.json(event["output"])
                if event.get("error"):
                    st.error(event["error"])

    with tab_claims:
        claims = run["unsupported_claims"]
        if not claims:
            st.success("No unsupported claims detected for this run.")
        for claim in claims:
            st.warning(f"{claim['task_id']}: {claim['claim']}")
            st.write(f"Verdict: `{claim['verdict']}` | Severity: `{claim['severity']}`")
            st.write(claim["reason"])

    with tab_compare:
        other = st.selectbox("Compare against", runs, format_func=lambda path: path.name, index=0)
        other_run = _load_run(other)
        left = summary
        right = other_run["summary"]
        st.write(f"Selected: `{selected.name}`")
        st.write(f"Other: `{other.name}`")
        cols = st.columns(3)
        cols[0].metric("Overall delta", round(right["overall_score"] - left["overall_score"], 3))
        cols[1].metric("Unsupported claim delta", right["unsupported_claim_count"] - left["unsupported_claim_count"])
        cols[2].metric("High-severity delta", right["high_severity_claim_count"] - left["high_severity_claim_count"])
        dimensions = sorted(set(left["dimension_averages"]) | set(right["dimension_averages"]))
        st.dataframe(
            [
                {
                    "dimension": dimension,
                    selected.name: left["dimension_averages"].get(dimension, 0.0),
                    other.name: right["dimension_averages"].get(dimension, 0.0),
                    "delta": round(
                        right["dimension_averages"].get(dimension, 0.0)
                        - left["dimension_averages"].get(dimension, 0.0),
                        3,
                    ),
                }
                for dimension in dimensions
            ],
            use_container_width=True,
        )


if __name__ == "__main__":
    main()
