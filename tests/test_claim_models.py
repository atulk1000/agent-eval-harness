import unittest

from agenteval.claim_eval.models import (
    RecordValidationError,
    claim_id,
    stable_id,
    validate_annotation,
    validate_claim,
    validate_evidence,
    validate_judge_call,
    validate_verdict,
)


class ClaimModelTests(unittest.TestCase):
    def test_stable_id_is_deterministic(self):
        self.assertEqual(stable_id("item", "A", 1), stable_id("item", "a", 1))

    def test_stable_id_changes_with_input(self):
        self.assertNotEqual(stable_id("item", "a"), stable_id("item", "b"))

    def test_claim_id_contains_task_and_ordinal(self):
        identifier = claim_id("task-one", 2, "Acme is active.")
        self.assertTrue(identifier.startswith("claim_task_one_02_"))

    def test_valid_claim_is_accepted(self):
        claim = _claim()
        self.assertIs(validate_claim(claim), claim)

    def test_claim_rejects_unknown_type(self):
        claim = _claim()
        claim["claim_type"] = "opinion"
        with self.assertRaises(RecordValidationError):
            validate_claim(claim)

    def test_claim_rejects_zero_ordinal(self):
        claim = _claim()
        claim["ordinal"] = 0
        with self.assertRaises(RecordValidationError):
            validate_claim(claim)

    def test_evidence_requires_matching_provenance(self):
        evidence = _evidence()
        evidence["provenance"]["trace_run_id"] = "other"
        with self.assertRaises(RecordValidationError):
            validate_evidence(evidence)

    def test_verdict_rejects_confidence_above_one(self):
        verdict = _verdict()
        verdict["confidence"] = 1.1
        with self.assertRaises(RecordValidationError):
            validate_verdict(verdict)

    def test_judge_call_rejects_unknown_status(self):
        call = _judge_call()
        call["status"] = "maybe"
        with self.assertRaises(RecordValidationError):
            validate_judge_call(call)

    def test_annotation_requires_rationale(self):
        annotation = _annotation()
        annotation["rationale"] = ""
        with self.assertRaises(RecordValidationError):
            validate_annotation(annotation)


def _claim():
    return {
        "schema_version": "1.0",
        "claim_id": "claim_1",
        "run_id": "run_1",
        "task_id": "task_1",
        "ordinal": 1,
        "text": "Acme is active.",
        "source_text": "Acme is active.",
        "source_span": {"start": 0, "end": 15},
        "claim_type": "business_status",
        "assertion_mode": "asserted",
        "source_requirement": "sql",
        "extractor": {"kind": "deterministic"},
    }


def _evidence():
    return {
        "schema_version": "1.0",
        "evidence_id": "evidence_1",
        "run_id": "run_1",
        "task_id": "task_1",
        "source_type": "sql_row",
        "tool": "sql_query",
        "tool_step": 1,
        "content": "customer=Acme",
        "structured_payload": {"customer": "Acme"},
        "provenance": {"trace_run_id": "run_1"},
    }


def _verdict():
    return {
        "schema_version": "1.0",
        "claim_id": "claim_1",
        "run_id": "run_1",
        "task_id": "task_1",
        "verdict": "supported",
        "confidence": 0.9,
        "reason": "Matched.",
        "evidence_refs": ["evidence_1"],
        "evidence_considered": ["evidence_1"],
        "unsupported_parts": [],
        "risk_level": "low",
        "severity": "none",
        "judge_path": "deterministic",
        "severity_reason": "Supported.",
        "requires_review": False,
    }


def _judge_call():
    return {
        "schema_version": "1.0",
        "judge_call_id": "judge_1",
        "claim_id": "claim_1",
        "provider": "mock",
        "model": "mock-v1",
        "prompt_version": "v1",
        "temperature": 0,
        "cache_key": "sha256:x",
        "cache_hit": False,
        "status": "success",
        "latency_ms": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_cost": 0,
        "redacted": False,
        "error": None,
    }


def _annotation():
    return {
        "schema_version": "1.0",
        "annotation_id": "annotation_1",
        "claim_id": "claim_1",
        "reviewer_id": "reviewer_1",
        "verdict": "supported",
        "severity": "none",
        "evidence_refs": [],
        "rationale": "Matched.",
        "dataset_split": "development",
        "review_stage": "primary",
        "created_at": "2026-07-15T00:00:00+00:00",
    }


if __name__ == "__main__":
    unittest.main()
