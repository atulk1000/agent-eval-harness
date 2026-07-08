"""Command-line interface for AgentEval Harness."""

from __future__ import annotations

import argparse
from pathlib import Path

from agenteval.reports.compare import compare_run_dirs
from agenteval.runner import run_suite, score_trace_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agenteval", description="Trace-based evals for SQL + RAG agents.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run a benchmark suite against a built-in agent.")
    run.add_argument("benchmark", help="Path to benchmark YAML/JSON file.")
    run.add_argument("--agent", default="improved_agent", help="Agent name: baseline_agent or improved_agent.")
    run.add_argument("--out", help="Optional output run directory.")

    score = subparsers.add_parser("score", help="Score an imported trace file.")
    score.add_argument("--trace", required=True, help="Path to traces.jsonl.")
    score.add_argument("--benchmark", required=True, help="Path to benchmark YAML/JSON file.")
    score.add_argument("--agent-name", default="external_trace", help="Name to use in summary artifacts.")
    score.add_argument("--out", help="Optional output run directory.")

    compare = subparsers.add_parser("compare", help="Compare two run directories.")
    compare.add_argument("left_run_dir")
    compare.add_argument("right_run_dir")
    compare.add_argument("--out", help="Optional output directory for comparison artifacts.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        run_dir = run_suite(args.benchmark, args.agent, output_dir=args.out)
        print(f"Wrote run artifacts to {Path(run_dir).resolve()}")
        return 0
    if args.command == "score":
        run_dir = score_trace_file(
            args.benchmark,
            args.trace,
            output_dir=args.out,
            agent_name=args.agent_name,
        )
        print(f"Wrote scored trace artifacts to {Path(run_dir).resolve()}")
        return 0
    if args.command == "compare":
        comparison = compare_run_dirs(args.left_run_dir, args.right_run_dir, out_dir=args.out)
        print(
            "Comparison complete: "
            f"overall delta={comparison['overall_score_delta']}, "
            f"unsupported claim delta={comparison['unsupported_claim_delta']}"
        )
        return 0
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
