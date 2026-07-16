import unittest

from agenteval.scorers import score_run


class ScoringTests(unittest.TestCase):
    def test_missing_required_tool_is_labeled(self):
        task = {
            "id": "t1",
            "task_type": "hybrid_sql_rag",
            "expected_route": {
                "required_tools": ["schema_lookup", "sql_query", "rag_search"],
                "optional_tools": [],
                "forbidden_tools": [],
                "max_tool_calls": 4,
            },
            "expected_sql": {
                "required_tables": [],
                "expected_entities": [],
                "unexpected_entities": [],
            },
            "expected_documents": {"relevant_doc_ids": []},
            "expected_answer_terms": [],
            "unsupported_claim_traps": [],
            "rubric": {"tool_routing": 1},
        }
        run = {
            "task_id": "t1",
            "final_answer": "premature answer",
            "trace": [
                {"type": "tool_call", "tool": "schema_lookup", "success": True, "output": {}}
            ],
        }
        score = score_run(task, run)
        self.assertIn("missing_required_tool", score["failure_labels"])

    def test_unsupported_claim_trap_is_detected(self):
        task = {
            "id": "t2",
            "task_type": "sql_only",
            "expected_route": {"required_tools": [], "optional_tools": [], "forbidden_tools": []},
            "expected_sql": {
                "required_tables": [],
                "expected_entities": [],
                "unexpected_entities": [],
            },
            "expected_documents": {"relevant_doc_ids": []},
            "expected_answer_terms": [],
            "unsupported_claim_traps": [
                {
                    "pattern": "already churned",
                    "claim": "Customer already churned",
                    "severity": "high",
                    "reason": "No evidence.",
                }
            ],
            "rubric": {"faithfulness": 1},
        }
        run = {"task_id": "t2", "final_answer": "Acme already churned.", "trace": []}
        score = score_run(task, run)
        self.assertEqual(len(score["unsupported_claims"]), 1)
        self.assertLess(score["dimension_scores"]["faithfulness"], 1.0)


if __name__ == "__main__":
    unittest.main()
