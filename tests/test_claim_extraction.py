import unittest

from agenteval.claim_eval.cache import JudgeCache
from agenteval.claim_eval.extraction import CompositeClaimExtractor, DeterministicClaimExtractor


class ClaimExtractionTests(unittest.TestCase):
    def setUp(self):
        self.run = {"run_id": "run_1", "task_id": "task_1", "final_answer": ""}
        self.sql_task = {"id": "task_1", "task_type": "sql_only"}

    def extract(self, answer, task=None):
        self.run["final_answer"] = answer
        return DeterministicClaimExtractor().extract(self.run, task or self.sql_task)

    def test_compound_factual_clauses_are_split(self):
        claims = self.extract("Acme revenue declined, and Northstar revenue increased.")
        self.assertEqual(len(claims), 2)

    def test_entity_list_is_not_split(self):
        claims = self.extract("Acme, Northstar, and Omni had declining revenue.")
        self.assertEqual(len(claims), 1)

    def test_factual_clause_splits_from_recommendation(self):
        claims = self.extract("Acme has churned, so all should be treated as renewal risks.")
        self.assertEqual([claim["text"] for claim in claims], ["Acme has churned"])

    def test_caveated_claim_is_labeled(self):
        claim = self.extract("There is no evidence that Acme churned.")[0]
        self.assertEqual(claim["assertion_mode"], "caveated")

    def test_uncertain_claim_is_labeled(self):
        claim = self.extract("It is unknown whether Acme churned.")[0]
        self.assertEqual(claim["assertion_mode"], "uncertain")

    def test_markdown_cleanup_preserves_identifier_underscores(self):
        claim = self.extract("Based on `account_note_q2`, Acme has renewal risk.")[0]
        self.assertIn("account_note_q2", claim["text"])

    def test_nonfactual_recommendation_is_ignored(self):
        claims = self.extract("Consider reviewing the account.")
        self.assertEqual(claims, [])

    def test_sql_task_requires_sql_evidence(self):
        claim = self.extract("Acme had lower revenue.")[0]
        self.assertEqual(claim["source_requirement"], "sql")

    def test_rag_task_with_q2_still_requires_rag(self):
        task = {"id": "task_1", "task_type": "rag_only"}
        claim = self.extract("Omni faced Q2 integration failures.", task)[0]
        self.assertEqual(claim["source_requirement"], "rag")

    def test_ids_are_stable(self):
        first = self.extract("Acme has renewal risk.")[0]["claim_id"]
        second = self.extract("Acme has renewal risk.")[0]["claim_id"]
        self.assertEqual(first, second)

    def test_semantic_claim_is_merged(self):
        provider = _ExtractionProvider(
            [{"text": "Acme has renewal risk.", "claim_type": "business_status"}]
        )
        self.run["final_answer"] = "The situation suggests risk."
        claims = CompositeClaimExtractor(provider, cache=JudgeCache()).extract(
            self.run, self.sql_task
        )
        self.assertTrue(any(claim["extractor"]["kind"] == "semantic" for claim in claims))

    def test_invalid_semantic_output_falls_back(self):
        provider = _ExtractionProvider("invalid")
        self.run["final_answer"] = "Acme has renewal risk."
        claims = CompositeClaimExtractor(provider).extract(self.run, self.sql_task)
        self.assertEqual(len(claims), 1)
        self.assertTrue(claims[0]["extraction_warnings"])


class _ExtractionProvider:
    name = "mock_extractor"
    model = "mock-v1"

    def __init__(self, output):
        self.output = output

    def extract(self, answer):
        return self.output


if __name__ == "__main__":
    unittest.main()
