import json
import tempfile
import unittest
from pathlib import Path

from agenteval.schema import load_validated_trace_file, validate_trace_file

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class TraceSchemaTests(unittest.TestCase):
    def test_valid_trace_is_accepted(self):
        report = validate_trace_file(FIXTURES / "valid_trace.jsonl", allow_legacy=False)
        self.assertTrue(report.valid)
        self.assertEqual(len(report.rows), 1)
        self.assertEqual(report.rows[0]["schema_version"], "1.0")

    def test_legacy_trace_is_normalized_with_warning(self):
        report = validate_trace_file(FIXTURES / "legacy_trace.jsonl")
        self.assertTrue(report.valid)
        self.assertEqual(report.rows[0]["schema_version"], "1.0")
        self.assertEqual([warning.code for warning in report.warnings], ["legacy_schema_version"])

    def test_strict_version_rejects_legacy_trace(self):
        report = validate_trace_file(FIXTURES / "legacy_trace.jsonl", allow_legacy=False)
        self.assertFalse(report.valid)
        self.assertIn("invalid_field_type", {error.code for error in report.errors})

    def test_invalid_trace_reports_multiple_errors(self):
        report = validate_trace_file(FIXTURES / "invalid_trace.jsonl", allow_legacy=False)
        codes = {error.code for error in report.errors}
        self.assertFalse(report.valid)
        self.assertGreaterEqual(len(report.errors), 6)
        self.assertIn("unsupported_schema_version", codes)
        self.assertIn("invalid_datetime", codes)
        self.assertIn("missing_event_error", codes)
        self.assertIn("invalid_latency", codes)

    def test_duplicate_task_ids_are_rejected(self):
        row = json.loads((FIXTURES / "valid_trace.jsonl").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "duplicate.jsonl"
            trace_path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")
            report = validate_trace_file(trace_path)
        self.assertIn("duplicate_task_id", {error.code for error in report.errors})

    def test_non_increasing_steps_are_rejected(self):
        row = json.loads((FIXTURES / "valid_trace.jsonl").read_text(encoding="utf-8"))
        row["trace"][1]["step"] = 1
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "steps.jsonl"
            trace_path.write_text(json.dumps(row), encoding="utf-8")
            report = validate_trace_file(trace_path)
        codes = {error.code for error in report.errors}
        self.assertIn("duplicate_step", codes)
        self.assertIn("non_increasing_step", codes)

    def test_loader_returns_normalized_rows(self):
        rows = load_validated_trace_file(FIXTURES / "legacy_trace.jsonl")
        self.assertEqual(rows[0]["schema_version"], "1.0")


if __name__ == "__main__":
    unittest.main()
