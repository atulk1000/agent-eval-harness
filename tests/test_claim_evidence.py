import unittest

from agenteval.claim_eval.evidence import EvidenceSelector, TraceEvidenceBuilder


class ClaimEvidenceTests(unittest.TestCase):
    def test_sql_rows_become_individual_evidence(self):
        evidence = TraceEvidenceBuilder().build(
            _run("sql_query", {"rows": [{"name": "A"}, {"name": "B"}]})
        )
        self.assertEqual([item["source_type"] for item in evidence], ["sql_row", "sql_row"])

    def test_empty_sql_becomes_diagnostic_evidence(self):
        evidence = TraceEvidenceBuilder().build(_run("sql_query", {"rows": []}))
        self.assertEqual(evidence[0]["source_type"], "empty_result")

    def test_rag_documents_become_chunks(self):
        evidence = TraceEvidenceBuilder().build(
            _run("rag_search", {"documents": [{"doc_id": "d1", "text": "Policy text"}]})
        )
        self.assertEqual(evidence[0]["source_type"], "document_chunk")

    def test_rag_chunks_alias_is_supported(self):
        evidence = TraceEvidenceBuilder().build(_run("rag_search", {"chunks": [{"text": "Note"}]}))
        self.assertEqual(evidence[0]["content"], "Note")

    def test_document_lookup_becomes_opened_document(self):
        evidence = TraceEvidenceBuilder().build(
            _run("document_lookup", {"document": {"doc_id": "d1", "text": "Full text"}})
        )
        self.assertEqual(evidence[0]["source_type"], "opened_document")

    def test_failed_tool_becomes_error_evidence(self):
        run = _run("sql_query", {}, success=False)
        run["trace"][0]["error"] = "timeout"
        evidence = TraceEvidenceBuilder().build(run)
        self.assertEqual(evidence[0]["source_type"], "tool_error")

    def test_selector_prioritizes_subject_match(self):
        evidence = TraceEvidenceBuilder().build(
            _run("sql_query", {"rows": [{"customer": "Other"}, {"customer": "Acme"}]})
        )
        selected, _ = EvidenceSelector().select(_claim("Acme is active."), evidence)
        self.assertIn("Acme", selected[0]["content"])

    def test_selector_enforces_limit_and_reports_excluded(self):
        evidence = TraceEvidenceBuilder().build(
            _run("sql_query", {"rows": [{"customer": f"Acme {index}"} for index in range(5)]})
        )
        selected, metadata = EvidenceSelector(limit=2).select(_claim("Acme is active."), evidence)
        self.assertEqual(len(selected), 2)
        self.assertEqual(metadata["excluded_count"], 3)

    def test_evidence_ids_are_stable(self):
        first = TraceEvidenceBuilder().build(_run("sql_query", {"rows": [{"customer": "Acme"}]}))
        second = TraceEvidenceBuilder().build(_run("sql_query", {"rows": [{"customer": "Acme"}]}))
        self.assertEqual(first[0]["evidence_id"], second[0]["evidence_id"])


def _run(tool, output, success=True):
    return {
        "run_id": "run_1",
        "task_id": "task_1",
        "trace": [
            {
                "step": 1,
                "type": "tool_call",
                "tool": tool,
                "input": {"query": "select customer"},
                "output": output,
                "success": success,
                "error": None,
            }
        ],
    }


def _claim(text):
    return {
        "text": text,
        "subject": "Acme",
        "source_requirement": "sql",
    }


if __name__ == "__main__":
    unittest.main()
