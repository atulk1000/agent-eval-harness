import tempfile
import unittest
from pathlib import Path

from agenteval.data_loader import ensure_demo_data
from agenteval.tools import Toolset
from agenteval.trace import TraceRecorder


class ToolTests(unittest.TestCase):
    def test_sql_tool_rejects_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "demo.db"
            docs_path = Path(tmp) / "docs.json"
            ensure_demo_data(db_path, docs_path)
            recorder = TraceRecorder(task_id="t", agent_name="test", model="test")
            tools = Toolset(recorder, db_path=db_path, docs_path=docs_path)
            result = tools.sql_query("DROP TABLE customers")
            self.assertFalse(recorder.trace[-1]["success"])
            self.assertEqual(result["rows"], [])

    def test_rag_search_returns_expected_doc(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "demo.db"
            docs_path = Path(tmp) / "docs.json"
            ensure_demo_data(db_path, docs_path)
            recorder = TraceRecorder(task_id="t", agent_name="test", model="test")
            tools = Toolset(recorder, db_path=db_path, docs_path=docs_path)
            result = tools.rag_search("Acme Health early termination material breach", top_k=3)
            ids = {doc["doc_id"] for doc in result["documents"]}
            self.assertIn("contract_acme_2026", ids)


if __name__ == "__main__":
    unittest.main()
