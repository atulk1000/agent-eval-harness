import json
import sys
import tempfile
import unittest
from pathlib import Path

from agenteval.adapters.public_company import (
    PCAAdapterError,
    adapt_pca_response,
    adapt_pca_response_file,
    capture_pca_responses,
)
from agenteval.schema import validate_trace_file

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "public_company_research_assistant"


class PCAAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = [
            json.loads(line)
            for line in (EXAMPLE / "raw_responses.jsonl").read_text(encoding="utf-8").splitlines()
        ]

    def test_sql_response_maps_rows_and_tables(self):
        row = self.rows[0]
        trace = adapt_pca_response(row["task_id"], row["response"], capture=row)
        event = trace["trace"][0]
        self.assertEqual(event["tool"], "sql_query")
        self.assertEqual(event["output"]["rows"][0]["ticker"], "MSFT")
        self.assertEqual(event["output"]["tables_used"], ["company_metrics"])

    def test_rag_response_maps_document_identity_and_text(self):
        row = self.rows[1]
        trace = adapt_pca_response(row["task_id"], row["response"], capture=row)
        document = trace["trace"][0]["output"]["documents"][0]
        self.assertEqual(document["doc_id"], "GOOGL_10-Q_ai_commentary_1")
        self.assertIn("AI investment", document["text"])

    def test_route_without_evidence_does_not_create_fake_events(self):
        response = {
            "status": "success",
            "route": "hybrid",
            "structured_evidence": None,
            "retrieved_evidence": [],
            "answer": "No evidence was returned.",
        }
        trace = adapt_pca_response("empty", response)
        self.assertEqual(trace["trace"], [])

    def test_summary_only_response_is_rejected(self):
        with self.assertRaisesRegex(PCAAdapterError, "summary booleans"):
            adapt_pca_response("summary", {"answer": "x", "sql_present": True})

    def test_response_file_adapts_and_validates_three_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "traces.jsonl"
            count = adapt_pca_response_file(
                EXAMPLE / "raw_responses.jsonl", EXAMPLE / "benchmark.json", output
            )
            report = validate_trace_file(output, allow_legacy=False)
        self.assertEqual(count, 3)
        self.assertTrue(report.valid)
        self.assertEqual([len(row["trace"]) for row in report.rows], [1, 1, 2])

    def test_capture_worker_runs_in_external_python_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pca_repo = root / "pca"
            agent_dir = pca_repo / "agent"
            agent_dir.mkdir(parents=True)
            (agent_dir / "__init__.py").write_text("", encoding="utf-8")
            (agent_dir / "hybrid_tool.py").write_text(
                "def answer_question(question, live_analysis=False, return_trace=False):\n"
                "    return {\n"
                "        'status': 'success', 'route': 'sql',\n"
                "        'structured_evidence': {'sql': 'SELECT 1', 'rows': [{'value': 1}]},\n"
                "        'retrieved_evidence': [], 'answer': question,\n"
                "        'agent_trace': {'return_trace': return_trace},\n"
                "    }\n",
                encoding="utf-8",
            )
            output = root / "responses.jsonl"
            count = capture_pca_responses(
                pca_repo,
                EXAMPLE / "benchmark.json",
                output,
                pca_python=sys.executable,
            )
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(count, 3)
        self.assertEqual(len(rows), 3)
        self.assertTrue(rows[0]["response"]["agent_trace"]["return_trace"])


if __name__ == "__main__":
    unittest.main()
