import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from agenteval.claim_eval.annotations import create_annotation
from agenteval.claim_eval.judging import CompositeClaimJudge
from agenteval.claim_eval.providers import MockJudgeProvider

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
PCA_PROOF = ROOT / "examples" / "public_company_research_assistant" / "proof"


class ArtifactSchemaTests(unittest.TestCase):
    def test_published_schemas_are_valid_draft_2020_12(self):
        for path in SCHEMAS.glob("*_v1_0.schema.json"):
            Draft202012Validator.check_schema(_json(path))

    def test_checked_in_claim_matches_schema(self):
        _validate("claim_v1_0.schema.json", _first_jsonl(PCA_PROOF / "claims.jsonl"))

    def test_checked_in_evidence_matches_schema(self):
        _validate("evidence_v1_0.schema.json", _first_jsonl(PCA_PROOF / "evidence.jsonl"))

    def test_checked_in_verdict_matches_schema(self):
        _validate(
            "claim_verdict_v1_0.schema.json",
            _first_jsonl(PCA_PROOF / "claim_verdicts.jsonl"),
        )

    def test_semantic_judge_call_matches_schema(self):
        claim = _claim()
        evidence = [_evidence()]
        provider = MockJudgeProvider(
            default={
                "verdict": "supported",
                "confidence": 0.9,
                "reason": "Matched.",
                "evidence_refs": ["evidence_1"],
                "unsupported_parts": [],
            }
        )
        _, calls = CompositeClaimJudge(provider).judge(
            claim,
            evidence,
            {"id": "task_1", "task_type": "hybrid_sql_rag"},
            {"candidate_limit": 8, "candidate_count": 1, "excluded_count": 0},
        )
        _validate("judge_call_v1_0.schema.json", calls[0])

    def test_human_annotation_matches_schema(self):
        annotation = create_annotation(
            claim_id="claim_1",
            reviewer_id="reviewer_1",
            verdict="supported",
            severity="none",
            evidence_refs=["evidence_1"],
            rationale="The evidence directly supports the claim.",
            dataset_split="held_out",
            review_stage="independent",
            created_at="2026-07-15T00:00:00+00:00",
        )
        _validate("annotation_v1_0.schema.json", annotation)


def _validate(schema_name, record):
    schema = _json(SCHEMAS / schema_name)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(record)


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _first_jsonl(path):
    return json.loads(next(line for line in path.read_text(encoding="utf-8").splitlines() if line))


def _claim():
    text = "Acme has renewal risk because onboarding failed."
    return {
        "schema_version": "1.0",
        "claim_id": "claim_1",
        "run_id": "run_1",
        "task_id": "task_1",
        "ordinal": 1,
        "text": text,
        "source_text": text,
        "source_span": {"start": 0, "end": len(text)},
        "claim_type": "causal",
        "assertion_mode": "asserted",
        "subject": "Acme",
        "source_requirement": "any",
        "extractor": {"kind": "deterministic"},
    }


def _evidence():
    return {
        "schema_version": "1.0",
        "evidence_id": "evidence_1",
        "run_id": "run_1",
        "task_id": "task_1",
        "source_type": "document_chunk",
        "tool": "rag_search",
        "tool_step": 1,
        "content": "Acme onboarding note",
        "structured_payload": {},
        "provenance": {"trace_run_id": "run_1", "event_step": 1},
    }


if __name__ == "__main__":
    unittest.main()
