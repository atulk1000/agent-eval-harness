import tempfile
import unittest
from pathlib import Path

from agenteval.claim_eval.cache import JudgeCache
from agenteval.claim_eval.judging import CompositeClaimJudge, DeterministicClaimJudge, JudgeBudget
from agenteval.claim_eval.providers import MockJudgeProvider, RuleOnlyJudgeProvider
from agenteval.claim_eval.scoring import aggregate_claim_scores


class DeterministicJudgingTests(unittest.TestCase):
    def test_no_evidence_abstains(self):
        result = DeterministicClaimJudge().judge(_claim("Acme is active."), [])
        self.assertEqual(result["verdict"], "not_enough_evidence")

    def test_evidence_caveat_is_supported_when_positive_fact_is_absent(self):
        claim = _claim(
            "There is no evidence that Acme churned.",
            assertion_mode="caveated",
            source_requirement="any",
        )
        result = DeterministicClaimJudge().judge(
            claim, [_evidence("Acme has renewal risk.", "document_chunk")]
        )
        self.assertEqual(result["verdict"], "supported")

    def test_missing_required_source_abstains(self):
        claim = _claim("Policy requires approval.", source_requirement="rag")
        result = DeterministicClaimJudge().judge(claim, [_evidence("approval=true", "sql_row")])
        self.assertEqual(result["verdict"], "not_enough_evidence")

    def test_structured_status_conflict_is_contradicted(self):
        claim = _claim("Acme has churned.", claim_type="business_status")
        evidence = _evidence(
            "customer=Acme, status=active", payload={"customer": "Acme", "status": "active"}
        )
        result = DeterministicClaimJudge().judge(claim, [evidence])
        self.assertEqual(result["verdict"], "contradicted")
        self.assertTrue(result["structured"])

    def test_structured_numeric_conflict_is_contradicted(self):
        claim = _claim("Acme revenue is 120.", claim_type="numeric")
        evidence = _evidence(
            "customer=Acme, revenue=100", payload={"customer": "Acme", "revenue": 100}
        )
        result = DeterministicClaimJudge().judge(claim, [evidence])
        self.assertEqual(result["verdict"], "contradicted")

    def test_exact_numeric_claim_is_supported(self):
        claim = _claim("Acme revenue is 100.", claim_type="numeric")
        evidence = _evidence(
            "customer=Acme, revenue=100", payload={"customer": "Acme", "revenue": 100}
        )
        result = DeterministicClaimJudge().judge(claim, [evidence])
        self.assertEqual(result["verdict"], "supported")

    def test_missing_numeric_detail_is_partial(self):
        claim = _claim("Acme revenue declined 12 percent.", claim_type="numeric")
        result = DeterministicClaimJudge().judge(claim, [_evidence("Acme revenue declined")])
        self.assertEqual(result["verdict"], "partially_supported")

    def test_unrelated_evidence_is_unsupported(self):
        claim = _claim("Acme was automatically approved.", source_requirement="any")
        result = DeterministicClaimJudge().judge(
            claim, [_evidence("Northstar had integration issues")]
        )
        self.assertEqual(result["verdict"], "unsupported")


class CompositeJudgingTests(unittest.TestCase):
    def setUp(self):
        self.claim = _claim(
            "Acme has renewal risk because onboarding failed.",
            claim_type="causal",
            source_requirement="any",
        )
        self.evidence = [_evidence("Acme onboarding note")]
        self.task = {"id": "task_1", "task_type": "hybrid_sql_rag"}
        self.selection = {"candidate_limit": 8, "candidate_count": 1, "excluded_count": 0}

    def test_rule_only_unresolved_claim_needs_review(self):
        verdict, calls = CompositeClaimJudge(RuleOnlyJudgeProvider()).judge(
            self.claim, self.evidence, self.task, self.selection
        )
        self.assertTrue(verdict["requires_review"])
        self.assertEqual(calls, [])

    def test_semantic_provider_resolves_unresolved_claim(self):
        provider = MockJudgeProvider(default=_semantic_output("supported"))
        verdict, calls = CompositeClaimJudge(provider).judge(
            self.claim, self.evidence, self.task, self.selection
        )
        self.assertEqual(verdict["judge_path"], "semantic")
        self.assertEqual(len(calls), 1)

    def test_invalid_semantic_output_needs_review(self):
        provider = MockJudgeProvider(default={"verdict": "maybe", "confidence": 1, "reason": "x"})
        verdict, calls = CompositeClaimJudge(provider).judge(
            self.claim, self.evidence, self.task, self.selection
        )
        self.assertTrue(verdict["requires_review"])
        self.assertEqual(calls[0]["status"], "invalid_output")

    def test_provider_timeout_needs_review(self):
        provider = MockJudgeProvider(failure="timeout")
        verdict, calls = CompositeClaimJudge(provider).judge(
            self.claim, self.evidence, self.task, self.selection
        )
        self.assertTrue(verdict["requires_review"])
        self.assertEqual(calls[0]["status"], "timeout")

    def test_semantic_cache_prevents_second_provider_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = MockJudgeProvider(default=_semantic_output("supported"))
            judge = CompositeClaimJudge(provider, cache=JudgeCache(Path(tmp) / "cache.json"))
            judge.judge(self.claim, self.evidence, self.task, self.selection)
            _, second_calls = judge.judge(self.claim, self.evidence, self.task, self.selection)
        self.assertEqual(provider.calls, 1)
        self.assertTrue(second_calls[0]["cache_hit"])

    def test_budget_exhaustion_needs_review(self):
        provider = MockJudgeProvider(default=_semantic_output("supported"))
        judge = CompositeClaimJudge(provider, budget=JudgeBudget(max_calls=0))
        verdict, calls = judge.judge(self.claim, self.evidence, self.task, self.selection)
        self.assertTrue(verdict["requires_review"])
        self.assertEqual(calls[0]["status"], "budget_exhausted")

    def test_structured_contradiction_cannot_be_overturned(self):
        provider = MockJudgeProvider(default=_semantic_output("supported"))
        claim = _claim("Acme has churned.", claim_type="business_status")
        evidence = [
            _evidence(
                "customer=Acme, status=active", payload={"customer": "Acme", "status": "active"}
            )
        ]
        verdict, calls = CompositeClaimJudge(provider).judge(
            claim, evidence, self.task, self.selection
        )
        self.assertEqual(verdict["verdict"], "contradicted")
        self.assertEqual(provider.calls, 0)
        self.assertEqual(calls, [])


class ClaimScoringTests(unittest.TestCase):
    def test_no_claims_is_not_applicable(self):
        metrics = aggregate_claim_scores([], [])
        self.assertEqual(metrics["status"], "not_applicable")
        self.assertIsNone(metrics["score"])

    def test_high_severity_issue_hard_fails(self):
        claims = [_claim("Acme churned.", claim_type="business_status")]
        verdicts = [_final_verdict("unsupported", "high", "high")]
        metrics = aggregate_claim_scores(claims, verdicts)
        self.assertEqual(metrics["status"], "fail")
        self.assertTrue(metrics["hard_gate_failures"])

    def test_unresolved_medium_risk_needs_review(self):
        claims = [_claim("Pricing caused decline.", claim_type="causal")]
        verdict = _final_verdict("not_enough_evidence", "medium", "medium")
        verdict["requires_review"] = True
        metrics = aggregate_claim_scores(claims, [verdict])
        self.assertEqual(metrics["status"], "needs_review")


def _claim(
    text,
    *,
    claim_type="entity_fact",
    assertion_mode="asserted",
    source_requirement="sql",
):
    return {
        "schema_version": "1.0",
        "claim_id": "claim_1",
        "run_id": "run_1",
        "task_id": "task_1",
        "ordinal": 1,
        "text": text,
        "source_text": text,
        "source_span": {"start": 0, "end": len(text)},
        "claim_type": claim_type,
        "assertion_mode": assertion_mode,
        "subject": "Acme",
        "source_requirement": source_requirement,
    }


def _evidence(content, source_type="sql_row", payload=None):
    return {
        "schema_version": "1.0",
        "evidence_id": "evidence_1",
        "run_id": "run_1",
        "task_id": "task_1",
        "source_type": source_type,
        "tool": "sql_query" if source_type == "sql_row" else "rag_search",
        "tool_step": 1,
        "content": content,
        "structured_payload": payload or {},
        "provenance": {"trace_run_id": "run_1", "event_step": 1},
    }


def _semantic_output(verdict):
    return {
        "verdict": verdict,
        "confidence": 0.9,
        "reason": "Semantic mock verdict.",
        "evidence_refs": ["evidence_1"],
        "unsupported_parts": [],
    }


def _final_verdict(verdict, severity, risk):
    return {
        "claim_id": "claim_1",
        "verdict": verdict,
        "severity": severity,
        "risk_level": risk,
        "requires_review": False,
    }


if __name__ == "__main__":
    unittest.main()
