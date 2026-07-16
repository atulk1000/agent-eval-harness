import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from agenteval.cli import main

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
PCA_EXAMPLE = ROOT / "examples" / "public_company_research_assistant"


class CLITests(unittest.TestCase):
    def test_validate_command_accepts_valid_trace(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(["validate", "--trace", str(FIXTURES / "valid_trace.jsonl")])
        self.assertEqual(result, 0)
        self.assertIn("Trace is valid", output.getvalue())

    def test_validate_command_rejects_invalid_trace(self):
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            result = main(["validate", "--trace", str(FIXTURES / "invalid_trace.jsonl")])
        self.assertEqual(result, 1)
        self.assertIn("unsupported_schema_version", error.getvalue())

    def test_adapt_pca_command_writes_valid_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "traces.jsonl"
            result = main(
                [
                    "adapt-pca",
                    "--responses",
                    str(PCA_EXAMPLE / "raw_responses.jsonl"),
                    "--benchmark",
                    str(PCA_EXAMPLE / "benchmark.json"),
                    "--out-trace",
                    str(output),
                ]
            )
            self.assertTrue(output.exists())
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
