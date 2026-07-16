"""End-to-end claim extraction, evidence linking, judgment, and scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agenteval.claim_eval.cache import JudgeCache
from agenteval.claim_eval.evidence import EvidenceSelector, TraceEvidenceBuilder
from agenteval.claim_eval.extraction import CompositeClaimExtractor, SemanticExtractionProvider
from agenteval.claim_eval.judging import CompositeClaimJudge, JudgeBudget
from agenteval.claim_eval.providers import RuleOnlyJudgeProvider, SemanticJudgeProvider
from agenteval.claim_eval.scoring import aggregate_claim_scores


@dataclass
class ClaimEvaluationConfig:
    provider: SemanticJudgeProvider | None = None
    semantic_extractor: SemanticExtractionProvider | None = None
    candidate_limit: int = 8
    max_semantic_calls: int = 50
    max_evidence_characters: int = 12000
    cache_path: str | Path | None = None
    _cache: JudgeCache | None = field(default=None, init=False, repr=False)
    _budget: JudgeBudget | None = field(default=None, init=False, repr=False)

    def reset_runtime(self) -> None:
        self._cache = JudgeCache(self.cache_path)
        self._budget = JudgeBudget(
            max_calls=self.max_semantic_calls,
            max_evidence_characters=self.max_evidence_characters,
        )

    def runtime(self) -> tuple[JudgeCache, JudgeBudget]:
        if self._cache is None or self._budget is None:
            self.reset_runtime()
        if self._cache is None or self._budget is None:
            raise RuntimeError("claim evaluation runtime did not initialize")
        return self._cache, self._budget


def evaluate_run_claims(
    task: dict[str, Any],
    run: dict[str, Any],
    config: ClaimEvaluationConfig | None = None,
) -> dict[str, Any]:
    config = config or ClaimEvaluationConfig()
    cache, budget = config.runtime()
    claims = CompositeClaimExtractor(config.semantic_extractor, cache=cache).extract(run, task)
    evidence = TraceEvidenceBuilder().build(run)
    selector = EvidenceSelector(config.candidate_limit)
    judge = CompositeClaimJudge(
        config.provider or RuleOnlyJudgeProvider(),
        cache=cache,
        budget=budget,
    )
    verdicts: list[dict[str, Any]] = []
    judge_calls: list[dict[str, Any]] = []
    for claim in claims:
        candidates, selection = selector.select(claim, evidence)
        verdict, calls = judge.judge(claim, candidates, task, selection)
        verdicts.append(verdict)
        judge_calls.extend(calls)
    metrics = aggregate_claim_scores(claims, verdicts)
    return {
        "claims": claims,
        "evidence": evidence,
        "verdicts": verdicts,
        "judge_calls": judge_calls,
        "metrics": metrics,
    }
