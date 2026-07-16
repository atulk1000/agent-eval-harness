"""Command-line interface for AgentEval Harness."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from agenteval.adapters.public_company import (
    PCAAdapterError,
    adapt_pca_response_file,
    capture_pca_responses,
)
from agenteval.claim_eval.annotations import adjudicate_annotations
from agenteval.claim_eval.calibration import build_calibration_dataset
from agenteval.claim_eval.metrics import run_calibration
from agenteval.claim_eval.pipeline import ClaimEvaluationConfig
from agenteval.claim_eval.providers import OpenAICompatibleJudgeProvider
from agenteval.reports.compare import compare_run_dirs
from agenteval.runner import run_suite, score_trace_file
from agenteval.schema import TraceValidationError, validate_trace_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agenteval", description="Trace-based evals for SQL + RAG agents."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run a benchmark suite against a built-in agent.")
    run.add_argument("benchmark", help="Path to benchmark YAML/JSON file.")
    run.add_argument(
        "--agent", default="improved_agent", help="Agent name: baseline_agent or improved_agent."
    )
    run.add_argument("--out", help="Optional output run directory.")
    _add_judge_arguments(run)

    score = subparsers.add_parser("score", help="Score an imported trace file.")
    score.add_argument("--trace", required=True, help="Path to traces.jsonl.")
    score.add_argument("--benchmark", required=True, help="Path to benchmark YAML/JSON file.")
    score.add_argument(
        "--agent-name", default="external_trace", help="Name to use in summary artifacts."
    )
    score.add_argument("--out", help="Optional output run directory.")
    _add_judge_arguments(score)

    compare = subparsers.add_parser("compare", help="Compare two run directories.")
    compare.add_argument("left_run_dir")
    compare.add_argument("right_run_dir")
    compare.add_argument("--out", help="Optional output directory for comparison artifacts.")

    validate = subparsers.add_parser(
        "validate", help="Validate a versioned external trace JSONL file."
    )
    validate.add_argument("--trace", required=True, help="Path to traces.jsonl.")
    validate.add_argument(
        "--strict-version",
        action="store_true",
        help="Reject legacy rows that omit schema_version.",
    )

    adapt_pca = subparsers.add_parser(
        "adapt-pca", help="Convert raw Public Company Research Assistant responses to traces."
    )
    adapt_pca.add_argument("--responses", required=True, help="Raw PCA response JSONL.")
    adapt_pca.add_argument("--benchmark", required=True, help="AgentEval benchmark file.")
    adapt_pca.add_argument("--out-trace", required=True, help="Output AgentEval trace JSONL.")

    capture_pca = subparsers.add_parser(
        "capture-pca", help="Capture raw PCA responses using the PCA repository environment."
    )
    capture_pca.add_argument("--pca-repo", required=True, help="Path to the PCA repository.")
    capture_pca.add_argument("--benchmark", required=True, help="AgentEval benchmark file.")
    capture_pca.add_argument("--out-responses", required=True, help="Output raw response JSONL.")
    capture_pca.add_argument(
        "--pca-python",
        help="Python executable with PCA dependencies; defaults to the current interpreter.",
    )

    build_calibration = subparsers.add_parser(
        "build-calibration", help="Build the proposed 100-case claim-faithfulness dataset."
    )
    build_calibration.add_argument(
        "--out", required=True, help="Output calibration dataset directory."
    )

    calibrate = subparsers.add_parser(
        "calibrate", help="Measure machine proposals against adjudicated human gold labels."
    )
    calibrate.add_argument("--dataset", required=True, help="Calibration dataset directory.")
    calibrate.add_argument("--out", required=True, help="Output calibration report directory.")

    adjudicate = subparsers.add_parser(
        "adjudicate", help="Create gold labels from human annotation JSONL files."
    )
    adjudicate.add_argument("--annotations", required=True, help="Annotation file or directory.")
    adjudicate.add_argument("--out", required=True, help="Output gold.jsonl path.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            run_dir = run_suite(
                args.benchmark,
                args.agent,
                output_dir=args.out,
                claim_config=_claim_config(args),
            )
            print(f"Wrote run artifacts to {Path(run_dir).resolve()}")
            return 0
        if args.command == "score":
            run_dir = score_trace_file(
                args.benchmark,
                args.trace,
                output_dir=args.out,
                agent_name=args.agent_name,
                claim_config=_claim_config(args),
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
        if args.command == "validate":
            report = validate_trace_file(args.trace, allow_legacy=not args.strict_version)
            for warning in report.warnings:
                print(f"WARNING: {warning.format()}")
            if not report.valid:
                for error in report.errors:
                    print(f"ERROR: {error.format()}", file=sys.stderr)
                print(
                    f"Trace validation failed: {len(report.errors)} error(s), "
                    f"{len(report.warnings)} warning(s).",
                    file=sys.stderr,
                )
                return 1
            print(
                f"Trace is valid: {len(report.rows)} run(s), "
                f"schema version 1.0, {len(report.warnings)} warning(s)."
            )
            return 0
        if args.command == "adapt-pca":
            count = adapt_pca_response_file(args.responses, args.benchmark, args.out_trace)
            print(f"Adapted {count} PCA response(s) to {Path(args.out_trace).resolve()}")
            return 0
        if args.command == "capture-pca":
            count = capture_pca_responses(
                args.pca_repo,
                args.benchmark,
                args.out_responses,
                pca_python=args.pca_python,
            )
            print(f"Captured {count} PCA response(s) to {Path(args.out_responses).resolve()}")
            return 0
        if args.command == "build-calibration":
            manifest = build_calibration_dataset(args.out)
            print(
                f"Built {manifest['case_count']} proposed calibration case(s) at "
                f"{Path(args.out).resolve()}"
            )
            return 0
        if args.command == "calibrate":
            report = run_calibration(args.dataset, args.out)
            print(
                f"Calibration status={report['status']}, paired={report['paired_count']}, "
                f"report={Path(args.out).resolve()}"
            )
            return 0
        if args.command == "adjudicate":
            report = adjudicate_annotations(args.annotations, args.out)
            print(
                f"Adjudication complete: gold={report['gold_count']}, "
                f"unresolved={report['unresolved_count']}"
            )
            return 0
    except (PCAAdapterError, TraceValidationError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    parser.error(f"Unknown command: {args.command}")
    return 2


def _add_judge_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--judge-provider",
        choices=("rule", "openai-compatible"),
        default="rule",
        help="Optional semantic judge provider; deterministic rules always run first.",
    )
    parser.add_argument("--judge-model", help="Semantic judge model name.")
    parser.add_argument("--judge-endpoint", help="OpenAI-compatible API base URL.")
    parser.add_argument(
        "--judge-api-key-env",
        default="AGENTEVAL_JUDGE_API_KEY",
        help="Environment variable containing the provider API key.",
    )
    parser.add_argument("--judge-cache", help="Optional persistent semantic-judge cache JSON file.")
    parser.add_argument(
        "--judge-max-calls", type=int, default=50, help="Per-run semantic call budget."
    )
    parser.add_argument(
        "--judge-max-retries",
        type=int,
        default=1,
        help="Retries after a transient provider failure.",
    )


def _claim_config(args: argparse.Namespace) -> ClaimEvaluationConfig:
    provider = None
    if args.judge_provider == "openai-compatible":
        model = args.judge_model or os.getenv("AGENTEVAL_JUDGE_MODEL")
        endpoint = args.judge_endpoint or os.getenv("AGENTEVAL_JUDGE_ENDPOINT")
        if not model or not endpoint:
            raise ValueError(
                "openai-compatible judge requires --judge-model and --judge-endpoint "
                "or AGENTEVAL_JUDGE_MODEL and AGENTEVAL_JUDGE_ENDPOINT"
            )
        provider = OpenAICompatibleJudgeProvider(
            model=model,
            endpoint=endpoint,
            api_key=os.getenv(args.judge_api_key_env),
            max_retries=args.judge_max_retries,
        )
    return ClaimEvaluationConfig(
        provider=provider,
        semantic_extractor=provider,
        max_semantic_calls=args.judge_max_calls,
        cache_path=args.judge_cache,
    )


if __name__ == "__main__":
    raise SystemExit(main())
