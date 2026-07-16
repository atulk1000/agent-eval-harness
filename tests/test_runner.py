import json
import tempfile
import unittest
from pathlib import Path

from agenteval.runner import score_trace_file
from agenteval.schema import TraceValidationError

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class RunnerTests(unittest.TestCase):
    def test_valid_external_trace_scores_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = score_trace_file(
                ROOT / "benchmarks" / "customer_risk.yaml",
                FIXTURES / "valid_trace.jsonl",
                output_dir=Path(tmp) / "run",
                agent_name="fixture_agent",
            )
            summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["task_count"], 1)
        self.assertEqual(summary["passed"], 1)

    def test_unknown_task_id_is_rejected_before_scoring(self):
        row = json.loads((FIXTURES / "valid_trace.jsonl").read_text(encoding="utf-8"))
        row["task_id"] = "not_in_benchmark"
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "unknown.jsonl"
            trace_path.write_text(json.dumps(row), encoding="utf-8")
            with self.assertRaisesRegex(TraceValidationError, "unknown benchmark task_id"):
                score_trace_file(ROOT / "benchmarks" / "customer_risk.yaml", trace_path)

    def test_malformed_trace_is_rejected_before_scoring(self):
        with self.assertRaises(TraceValidationError):
            score_trace_file(
                ROOT / "benchmarks" / "customer_risk.yaml",
                FIXTURES / "invalid_trace.jsonl",
            )


if __name__ == "__main__":
    unittest.main()
