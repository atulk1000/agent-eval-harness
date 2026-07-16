# AgentEval Report: proof

## Overview

- Suite: `public_company_research_assistant_bridge_v1`
- Agent: `public_company_research_assistant`
- Tasks: 3
- Passed: 1
- Failed: 1
- Needs review: 1
- Overall score: 0.97
- Extracted claims: 5
- Unsupported claims: 3
- High-severity unsupported claims: 0

## Dimension Averages

- completeness: 1.0
- efficiency: 1.0
- expected_facts: 1.0
- faithfulness: 0.625
- retrieval_grounding: 1.0
- source_attribution: 0.833
- sql_correctness: 1.0
- synthesis: 0.85
- tool_routing: 1.0
- trace_health: 1.0

## Task Results

### pca_sql_margin

- Type: `sql_only`
- Status: `fail`
- Overall score: 1.0
- Actual route: sql_query
- Failure labels: unsupported_claim
- Unsupported claims: 1
- Claim verdicts: {'partially_supported': 1}

  - Claim: Microsoft had the highest operating margin in the supplied structured result.
    - Verdict: partially_supported
    - Severity: low
    - Reason: The evidence supports the core topic but not every material qualifier.

### pca_rag_ai_themes

- Type: `rag_only`
- Status: `pass`
- Overall score: 1.0
- Actual route: rag_search
- Failure labels: none
- Unsupported claims: 0
- Claim verdicts: {'supported': 1}

### pca_hybrid_cloud

- Type: `hybrid_sql_rag`
- Status: `needs_review`
- Overall score: 0.91
- Actual route: sql_query -> rag_search
- Failure labels: unsupported_claim, claim_needs_review
- Unsupported claims: 2
- Claim verdicts: {'not_enough_evidence': 1, 'partially_supported': 1, 'supported': 1}

  - Claim: Structured data shows faster recent revenue growth for Microsoft in this evidence set.
    - Verdict: not_enough_evidence
    - Severity: medium
    - Reason: The trace contains related evidence, but semantic interpretation is required.
  - Claim: Filing excerpts connect Microsoft cloud demand to Azure
    - Verdict: partially_supported
    - Severity: low
    - Reason: The evidence supports the core topic but not every material qualifier.
