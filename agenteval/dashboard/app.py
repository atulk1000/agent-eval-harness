"""Streamlit operations and human-review dashboard."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from agenteval.claim_eval.annotations import create_annotation, load_annotations

ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = ROOT / "runs"
CALIBRATION_DIR = ROOT / "calibration"
PLAIN_VERDICTS = {
    "supported": "Fully supported",
    "partially_supported": "Only partly supported",
    "unsupported": "Evidence does not support this",
    "contradicted": "Evidence conflicts with this",
    "not_enough_evidence": "Cannot determine from available evidence",
}


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _run_dirs() -> list[Path]:
    if not RUNS_DIR.exists():
        return []
    return sorted(
        [path for path in RUNS_DIR.iterdir() if path.is_dir() and (path / "summary.json").exists()],
        reverse=True,
    )


def _calibration_dirs() -> list[Path]:
    if not CALIBRATION_DIR.exists():
        return []
    return sorted(
        [
            path
            for path in CALIBRATION_DIR.iterdir()
            if path.is_dir() and (path / "cases.jsonl").exists()
        ]
    )


def _load_run(run_dir: Path) -> dict[str, Any]:
    return {
        "dir": run_dir,
        "summary": _load_json(run_dir / "summary.json", {}),
        "scores": _load_json(run_dir / "scores.json", []),
        "unsupported_claims": _load_json(run_dir / "unsupported_claims.json", []),
        "traces": _load_jsonl(run_dir / "traces.jsonl"),
        "claims": _load_jsonl(run_dir / "claims.jsonl"),
        "evidence": _load_jsonl(run_dir / "evidence.jsonl"),
        "verdicts": _load_jsonl(run_dir / "claim_verdicts.jsonl"),
        "annotations": _load_jsonl(run_dir / "annotations.jsonl"),
        "claim_metrics": _load_json(run_dir / "claim_metrics.json", {}),
    }


def _load_calibration(dataset_dir: Path) -> dict[str, Any]:
    annotations_dir = dataset_dir / "annotations"
    annotations = load_annotations(annotations_dir) if annotations_dir.exists() else []
    return {
        "dir": dataset_dir,
        "manifest": _load_json(dataset_dir / "manifest.json", {}),
        "cases": _load_jsonl(dataset_dir / "cases.jsonl"),
        "proposals": _load_jsonl(dataset_dir / "proposals.jsonl"),
        "annotations": annotations,
        "report": _load_json(dataset_dir / "calibration_report.json", None),
    }


def _annotation_jsonl(rows: list[dict[str, Any]]) -> str:
    return "\n".join(json.dumps(row, sort_keys=True) for row in rows) + ("\n" if rows else "")


def _disagreements(annotations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for annotation in annotations:
        grouped[annotation["claim_id"]].append(annotation)
    rows = []
    for claim_id, records in sorted(grouped.items()):
        labels = sorted({record["verdict"] for record in records})
        if len(labels) > 1:
            rows.append(
                {
                    "claim_id": claim_id,
                    "reviewers": len({record["reviewer_id"] for record in records}),
                    "labels": ", ".join(labels),
                    "status": "needs adjudication",
                }
            )
    return rows


def main() -> None:
    try:
        import streamlit as st
    except ModuleNotFoundError:
        print("Streamlit is not installed. Install with: pip install -e .[dashboard]")
        return

    st.set_page_config(page_title="AgentEval Harness", layout="wide")
    st.title("AgentEval Harness")
    st.session_state.setdefault("review_annotations", [])
    reviewer_id = st.sidebar.text_input("Reviewer ID", value="reviewer_01")
    runs = _run_dirs()
    datasets = _calibration_dirs()

    tab_overview, tab_tasks, tab_trace, tab_claims, tab_calibration, tab_compare = st.tabs(
        [
            "Overview",
            "Task Results",
            "Trace & Evidence",
            "Claim Review",
            "Calibration",
            "Compare Runs",
        ]
    )

    selected_run = st.sidebar.selectbox(
        "Run",
        runs,
        format_func=lambda path: path.name,
        index=0 if runs else None,
        placeholder="No runs",
    )
    run = _load_run(selected_run) if selected_run else None

    with tab_overview:
        if run is None:
            st.info("No run artifacts found.")
        else:
            summary = run["summary"]
            cols = st.columns(6)
            cols[0].metric("Overall", summary.get("overall_score", 0))
            cols[1].metric("Passed", summary.get("passed", 0))
            cols[2].metric("Failed", summary.get("failed", 0))
            cols[3].metric("Needs Review", summary.get("needs_review", 0))
            cols[4].metric("Claims", summary.get("claim_count", 0))
            cols[5].metric("High Severity", summary.get("high_severity_claim_count", 0))
            st.subheader("Dimension Averages")
            st.dataframe(
                [
                    {"dimension": name, "score": value}
                    for name, value in summary.get("dimension_averages", {}).items()
                ],
                width="stretch",
                hide_index=True,
            )
            st.subheader("Claim Verdicts")
            st.json(summary.get("claim_verdict_counts", {}))

    with tab_tasks:
        if run is None:
            st.info("No run selected.")
        else:
            rows = []
            for score in run["scores"]:
                rows.append(
                    {
                        "task_id": score["task_id"],
                        "task_type": score["task_type"],
                        "status": score["status"],
                        "overall_score": score["overall_score"],
                        "faithfulness": score["dimension_scores"].get("faithfulness"),
                        "actual_route": " -> ".join(score["tool_routing"]["actual_route"]),
                        "failure_labels": ", ".join(score["failure_labels"]),
                    }
                )
            st.dataframe(rows, width="stretch", hide_index=True)

    with tab_trace:
        if run is None or not run["traces"]:
            st.info("No trace selected.")
        else:
            task_ids = [trace["task_id"] for trace in run["traces"]]
            selected_task = st.selectbox("Task", task_ids, key="trace_task")
            trace = next(item for item in run["traces"] if item["task_id"] == selected_task)
            score = next(item for item in run["scores"] if item["task_id"] == selected_task)
            st.subheader(selected_task)
            st.info(trace["final_answer"])
            st.json(score["dimension_scores"])
            for event in trace["trace"]:
                with st.expander(f"{event['step']}. {event['tool']}"):
                    left, right = st.columns(2)
                    left.json(event["input"])
                    right.json(event["output"])
                    if event.get("error"):
                        st.error(event["error"])

    with tab_claims:
        if run is None or not run["claims"]:
            st.info("No v1.3 claim artifacts found for this run.")
        else:
            claim_lookup = {claim["claim_id"]: claim for claim in run["claims"]}
            verdict_lookup = {verdict["claim_id"]: verdict for verdict in run["verdicts"]}
            evidence_lookup = {item["evidence_id"]: item for item in run["evidence"]}
            selected_claim_id = st.selectbox(
                "Claim",
                list(claim_lookup),
                format_func=lambda claim_id: claim_lookup[claim_id]["text"],
                key="run_claim",
            )
            claim = claim_lookup[selected_claim_id]
            verdict = verdict_lookup[selected_claim_id]
            evidence = [
                evidence_lookup[ref]
                for ref in verdict.get("evidence_considered", [])
                if ref in evidence_lookup
            ]
            trace = next(item for item in run["traces"] if item["task_id"] == claim["task_id"])
            _render_review(
                st,
                claim=claim,
                answer=trace["final_answer"],
                evidence=evidence,
                proposal=verdict,
                reviewer_id=reviewer_id,
                dataset_split="run",
                key_prefix="run",
                blind=False,
            )

    with tab_calibration:
        if not datasets:
            st.info("No calibration dataset found.")
        else:
            selected_dataset = st.selectbox(
                "Dataset", datasets, format_func=lambda path: path.name, key="dataset"
            )
            dataset = _load_calibration(selected_dataset)
            blind = st.toggle("Blind review", value=True)
            proposals = {row["claim_id"]: row for row in dataset["proposals"]}
            all_annotations = dataset["annotations"] + st.session_state["review_annotations"]
            reviewed_ids = {row["claim_id"] for row in all_annotations}
            cases = dataset["cases"]
            left, middle, right = st.columns(3)
            task_filter = left.selectbox(
                "Task type", ["all"] + sorted({case["task_type"] for case in cases})
            )
            split_filter = middle.selectbox(
                "Split", ["all", "development", "calibration", "held_out"]
            )
            review_filter = right.selectbox("Review status", ["pending", "reviewed", "all"])
            filtered = [
                case
                for case in cases
                if (task_filter == "all" or case["task_type"] == task_filter)
                and (split_filter == "all" or case["split"] == split_filter)
                and (
                    review_filter == "all"
                    or (review_filter == "reviewed") == (case["claim_id"] in reviewed_ids)
                )
            ]
            if not filtered:
                st.info("No cases match the selected filters.")
            else:
                selected_case = st.selectbox(
                    "Case",
                    filtered,
                    format_func=lambda case: f"{case['case_id']} | {case['claim']['text']}",
                    key="calibration_case",
                )
                _render_review(
                    st,
                    claim=selected_case["claim"],
                    answer=selected_case["final_answer"],
                    evidence=selected_case["evidence"],
                    proposal=None if blind else proposals.get(selected_case["claim_id"]),
                    reviewer_id=reviewer_id,
                    dataset_split=selected_case["split"],
                    key_prefix="calibration",
                    blind=blind,
                )
            disagreements = _disagreements(all_annotations)
            st.subheader("Disagreements")
            if disagreements:
                st.dataframe(disagreements, width="stretch", hide_index=True)
            else:
                st.write("No reviewer disagreements.")
            if dataset["report"]:
                st.subheader("Calibration Metrics")
                st.json(dataset["report"])

    with tab_compare:
        if run is None or not runs:
            st.info("No runs available for comparison.")
        else:
            other = st.selectbox(
                "Compare against", runs, format_func=lambda path: path.name, key="compare_run"
            )
            other_run = _load_run(other)
            left_summary = run["summary"]
            right_summary = other_run["summary"]
            cols = st.columns(3)
            cols[0].metric(
                "Overall delta",
                round(right_summary["overall_score"] - left_summary["overall_score"], 3),
            )
            cols[1].metric(
                "Claim delta",
                right_summary.get("claim_count", 0) - left_summary.get("claim_count", 0),
            )
            cols[2].metric(
                "Review delta",
                right_summary.get("needs_review", 0) - left_summary.get("needs_review", 0),
            )
            dimensions = sorted(
                set(left_summary.get("dimension_averages", {}))
                | set(right_summary.get("dimension_averages", {}))
            )
            st.dataframe(
                [
                    {
                        "dimension": dimension,
                        selected_run.name: left_summary["dimension_averages"].get(dimension),
                        other.name: right_summary["dimension_averages"].get(dimension),
                    }
                    for dimension in dimensions
                ],
                width="stretch",
                hide_index=True,
            )

    annotations = st.session_state["review_annotations"]
    st.sidebar.download_button(
        "Export annotations",
        data=_annotation_jsonl(annotations),
        file_name="annotations.jsonl",
        mime="application/x-ndjson",
        disabled=not annotations,
    )


def _render_review(
    st: Any,
    *,
    claim: dict[str, Any],
    answer: str,
    evidence: list[dict[str, Any]],
    proposal: dict[str, Any] | None,
    reviewer_id: str,
    dataset_split: str,
    key_prefix: str,
    blind: bool,
) -> None:
    st.subheader("Answer Context")
    st.info(answer)
    st.subheader("Claim")
    st.write(claim["text"])
    st.caption(
        f"Type: {claim['claim_type']} | Assertion: {claim['assertion_mode']} | Source: {claim['source_requirement']}"
    )
    if proposal is not None:
        st.subheader("Machine Assessment")
        cols = st.columns(3)
        cols[0].metric("Verdict", PLAIN_VERDICTS.get(proposal["verdict"], proposal["verdict"]))
        cols[1].metric("Confidence", proposal["confidence"])
        cols[2].metric("Severity", proposal["severity"])
        st.write(proposal["reason"])

    referenced = set(proposal.get("evidence_refs", [])) if proposal else set()
    sql_evidence = [item for item in evidence if item["source_type"] == "sql_row"]
    document_evidence = [
        item
        for item in evidence
        if item["source_type"]
        in {"document_chunk", "opened_document", "tool_error", "empty_result"}
    ]
    left, right = st.columns(2)
    _render_evidence_column(left, "SQL Evidence", sql_evidence, referenced)
    _render_evidence_column(right, "Document / Tool Evidence", document_evidence, referenced)

    options = list(PLAIN_VERDICTS)
    with st.form(f"{key_prefix}_{claim['claim_id']}", clear_on_submit=True):
        st.subheader("Human Label")
        verdict = st.selectbox(
            "Verdict",
            options,
            format_func=lambda value: PLAIN_VERDICTS[value],
            key=f"{key_prefix}_verdict_{claim['claim_id']}",
        )
        severity = st.selectbox(
            "Severity",
            ["none", "low", "medium", "high"],
            key=f"{key_prefix}_severity_{claim['claim_id']}",
        )
        evidence_refs = st.multiselect(
            "Evidence references",
            [item["evidence_id"] for item in evidence],
            key=f"{key_prefix}_evidence_{claim['claim_id']}",
        )
        review_stage = st.selectbox(
            "Review stage",
            ["primary", "independent", "adjudicator"],
            key=f"{key_prefix}_stage_{claim['claim_id']}",
        )
        rationale = st.text_area(
            "Rationale",
            key=f"{key_prefix}_rationale_{claim['claim_id']}",
        )
        submitted = st.form_submit_button("Add annotation", width="stretch")
    if submitted:
        if not reviewer_id.strip() or not rationale.strip():
            st.error("Reviewer ID and rationale are required.")
        else:
            annotation = create_annotation(
                claim_id=claim["claim_id"],
                reviewer_id=reviewer_id.strip(),
                verdict=verdict,
                severity=severity,
                evidence_refs=evidence_refs,
                rationale=rationale.strip(),
                dataset_split=dataset_split,
                review_stage=review_stage,
            )
            annotation["blind_review"] = blind
            st.session_state["review_annotations"].append(annotation)
            st.success("Annotation added.")


def _render_evidence_column(
    column: Any,
    title: str,
    evidence: list[dict[str, Any]],
    referenced: set[str],
) -> None:
    column.subheader(title)
    if not evidence:
        column.write("None")
        return
    for item in evidence:
        label = item["evidence_id"]
        with column.expander(label, expanded=item["evidence_id"] in referenced):
            if item["evidence_id"] in referenced:
                column.success("Referenced by machine verdict")
            column.write(item["content"])
            column.json(item.get("structured_payload", {}))


if __name__ == "__main__":
    main()
