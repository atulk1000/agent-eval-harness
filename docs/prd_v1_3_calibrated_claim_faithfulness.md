# AgentEval Harness v1.3

## Calibrated Claim-Faithfulness Release PRD

Status: Software implemented; human calibration pending

Release: v1.3

Package version: 1.3.0

Theme: Make faithfulness scores measurable, evidence-linked, and governable

Implementation plan: [v1_3_implementation_plan.md](v1_3_implementation_plan.md)

## 1. Release Summary

AgentEval v1.3 replaces the legacy regex-derived faithfulness scorer with a calibrated, claim-level evaluator. The evaluator extracts atomic factual claims from an agent answer, selects typed evidence from the trace, applies deterministic checks, optionally escalates unresolved semantic cases to a configured judge provider, and produces evidence-linked verdicts and policy-based severity.

The release also introduces a human-review workflow, a 100-case calibration dataset, held-out quality gates, and versioned claim-evaluation artifacts. Trace schema `1.0` remains the compatibility boundary for built-in and external agents.

The primary reviewer question for v1.3 is:

> Can this project demonstrate that its faithfulness judgments agree with independently reviewed evidence, rather than merely producing plausible scores?

## 2. Problem

v1.2 establishes a strong transport and provenance foundation:

- External traces are versioned and validated.
- SQL rows and retrieved chunks retain their source identity.
- The PCA bridge maps only evidence the external agent actually emitted.

However, the current faithfulness layer is not sufficiently general. It detects benchmark-authored phrase patterns, uses shallow keyword heuristics, and cannot reliably detect unexpected hallucinations, paraphrased claims, partial support, causal overreach, or semantic contradictions.

This creates four limitations:

1. A claim not anticipated by an unsupported-claim trap can be missed.
2. A detected claim does not reliably identify the evidence that supports or contradicts it.
3. The project cannot quantify judge precision, recall, or failure modes against human-reviewed labels.
4. A severe hallucination can be obscured by an otherwise high aggregate score.

v1.3 addresses these limitations without expanding into a generic evaluation platform.

## 3. Goals

- Make atomic factual claims the unit of faithfulness evaluation.
- Extract claims independently from benchmark expected answers and traps.
- Convert trace outputs into stable, typed evidence records.
- Select claim-specific evidence deterministically before semantic judgment.
- Support five strictly defined verdicts.
- Apply deterministic checks before any model call.
- Add an optional provider-neutral semantic judge for unresolved cases.
- Link every non-error verdict to the evidence considered.
- Assign severity through deterministic policy rather than model preference.
- Prevent high-risk failures from averaging away.
- Add `needs_review` as a first-class task status.
- Create a mixed 100-case calibration dataset with protected splits.
- Support primary review, independent held-out review, and adjudication in Streamlit.
- Publish per-stage metrics, confusion matrices, and release gates.
- Replace the legacy faithfulness scorer while preserving trace schema `1.0` compatibility.

## 4. Non-Goals

- Calibrating completeness, synthesis, or source-attribution judges.
- Preserving the legacy faithfulness scorer as an active runtime mode.
- Repeated model experiments or statistical model comparison across runs.
- Historical trend storage.
- Hosted annotation persistence.
- Authentication, roles, assignments, or team workspaces.
- Fine-tuning an extractor or judge.
- Requiring a paid semantic provider for offline evaluation.
- Supporting arbitrary agent frameworks beyond the existing trace contract.
- Evaluating hidden chain-of-thought.
- Claiming production readiness from a 100-case portfolio dataset.

## 5. Product Principles

- Judge only observable claims and evidence.
- Treat benchmark gold data as evaluation metadata, never judge context.
- Preserve provenance from tool event to evidence item to claim verdict.
- Prefer deterministic checks for structured facts.
- Use semantic judging only where language understanding is necessary.
- Never turn judge failure into a supported verdict.
- Separate machine verdicts, proposed labels, human annotations, and adjudicated gold.
- Make severe errors visible even when aggregate quality is high.
- Keep the default path local and standard-library-friendly.
- Be explicit about calibration limitations and reviewer coverage.

## 6. End-To-End Workflow

```text
validated AgentEval trace
  -> final answer preprocessing
  -> atomic claim extraction
  -> typed evidence construction
  -> claim-specific evidence selection
  -> deterministic claim checks
  -> optional semantic escalation
  -> verdict and confidence
  -> deterministic severity policy
  -> task score and hard gates
  -> artifacts, report, dashboard, calibration metrics
```

Hidden chain-of-thought is not required, captured, or evaluated.

## 7. Claim Contract

An atomic factual claim is one independently verifiable proposition. Compound sentences must be split when their components could receive different verdicts or evidence.

Example answer:

```text
Acme's revenue declined 12%, and account notes show it already churned.
```

Required claims:

```text
C1: Acme's revenue declined 12%.
C2: Account notes indicate Acme already churned.
```

Headings, commands, greetings, stylistic transitions, and non-factual recommendations are not claims. Explicit uncertainty statements may be retained as caveated claims when they make an evidence-related assertion.

### Claim Types

- `numeric`
- `entity_fact`
- `business_status`
- `policy_or_requirement`
- `causal`
- `comparative`
- `source_attribution`
- `descriptive`
- `other`

### Assertion Modes

- `asserted`
- `caveated`
- `uncertain`

### Claim Schema

```json
{
  "schema_version": "1.0",
  "claim_id": "claim_task_001_01_a41f82d0",
  "run_id": "run_abc123",
  "task_id": "task_001",
  "ordinal": 1,
  "text": "Acme's revenue declined 12%.",
  "source_text": "Acme's revenue declined 12%, and account notes show it already churned.",
  "source_span": {"start": 0, "end": 28},
  "claim_type": "numeric",
  "assertion_mode": "asserted",
  "subject": "Acme",
  "source_requirement": "sql",
  "extractor": {
    "kind": "semantic",
    "provider": "configured-provider",
    "model": "configured-model",
    "prompt_version": "claim_extraction_v1"
  }
}
```

Claim IDs must be deterministic for the same task, normalized text, and ordinal.

## 8. Claim Extraction

Claim extraction uses a hybrid architecture:

1. Remove display-only Markdown while retaining answer text and citation labels.
2. Split the answer into candidate sentences and clauses.
3. Run deterministic extraction for direct structured statements.
4. When configured, use a structured-output semantic extractor for compound or implicit claims.
5. Validate every extracted claim against the claim schema.
6. Deduplicate normalized claims.
7. Persist claims with extractor and prompt metadata.

The extractor receives only the final answer and extraction instructions. It must not receive expected answer terms, unsupported-claim traps, gold verdicts, or hidden reasoning.

Offline mode uses conservative deterministic extraction. Claims that cannot be safely separated are retained with an extraction warning rather than silently dropped.

## 9. Evidence Contract

Evidence is constructed only from successful or failed tool events in the trace the agent actually observed. The evaluator must not query the backing database, document corpus, or benchmark oracle to strengthen the agent's evidence after the fact.

### Evidence Types

- `sql_row`
- `document_chunk`
- `opened_document`
- `tool_error`
- `empty_result`

### Evidence Schema

```json
{
  "schema_version": "1.0",
  "evidence_id": "step_2.sql.row_0",
  "run_id": "run_abc123",
  "task_id": "task_001",
  "source_type": "sql_row",
  "tool": "sql_query",
  "tool_step": 2,
  "content": "customer=Acme, q1_revenue=100000, q2_revenue=88000",
  "structured_payload": {
    "customer": "Acme",
    "q1_revenue": 100000,
    "q2_revenue": 88000
  },
  "provenance": {
    "trace_run_id": "run_abc123",
    "event_step": 2
  }
}
```

Tool errors and empty results can establish insufficient evidence. They cannot support a positive factual assertion.

## 10. Evidence Selection

Candidate evidence is selected before semantic judgment using deterministic signals:

1. Exact subject and entity matches.
2. Exact numbers, dates, statuses, and identifiers.
3. Required source type from the claim.
4. Lexical overlap and normalized synonyms.
5. Source balancing for hybrid claims.
6. Stable rank order from the original trace.

The default candidate limit is eight evidence items per claim and must be configurable. Exact structured matches are retained before lower-ranked document chunks. Candidate selection must record excluded-count metadata so truncation remains visible.

## 11. Verdict Taxonomy

| Verdict | Operational Definition |
| --- | --- |
| `supported` | All material parts of the claim are directly supported by trace evidence. |
| `partially_supported` | The core claim is supported, but a material number, qualifier, cause, scope, or attribution is not. |
| `unsupported` | Relevant trace evidence exists but does not support the asserted fact. |
| `contradicted` | Trace evidence directly conflicts with the claim. |
| `not_enough_evidence` | The evaluator cannot decide reliably because evidence is missing, inaccessible, ambiguous, or affected by tool failure. |

`not_enough_evidence` is an evaluator abstention, not an automatic pass. A confident high-risk assertion remains a grounding failure when evidence is insufficient. A properly caveated statement about missing evidence is not treated as the underlying positive assertion.

### Verdict Schema

```json
{
  "schema_version": "1.0",
  "claim_id": "claim_task_001_01_a41f82d0",
  "verdict": "partially_supported",
  "confidence": 0.86,
  "reason": "Revenue declined, but the trace does not support the stated 12% figure.",
  "evidence_refs": ["step_2.sql.row_0"],
  "unsupported_parts": ["12%"],
  "judge_path": "deterministic",
  "risk_level": "medium",
  "severity": "medium",
  "severity_reason": "Material numeric detail is unsupported."
}
```

## 12. Composite Judge Architecture

The evaluator exposes these boundaries:

```text
ClaimExtractor
EvidenceBuilder
EvidenceSelector
DeterministicClaimJudge
SemanticClaimJudge
CompositeClaimJudge
SeverityPolicy
ClaimScoreAggregator
```

### Deterministic Checks

Deterministic evaluation handles:

- Exact numbers and configured numeric tolerances.
- Dates, statuses, and identifiers.
- Entity mismatches and cross-entity evidence use.
- Direct SQL field matches.
- Direct structured contradictions.
- Missing required source types.
- Empty results and tool failures.
- References to documents the agent did not retrieve.

Deterministic structured facts take precedence over semantic judgments. The semantic provider may explain but cannot overturn a decisive structured contradiction.

### Semantic Escalation

Semantic judgment is reserved for:

- Paraphrased document evidence.
- Partial support.
- Causal statements.
- Comparative claims.
- Cross-source synthesis.
- Semantic contradiction.
- Material qualifiers and attribution.

The provider must return validated structured output. Invalid output, timeout, exhausted budget, or unavailable provider never becomes `supported`.

## 13. Judge Provider Contract

Required providers:

- `RuleOnlyJudgeProvider`
- `MockJudgeProvider`
- `OpenAICompatibleJudgeProvider`

The implementation must not hardcode a production model. Provider and model are configuration values.

Every semantic call records:

```json
{
  "schema_version": "1.0",
  "judge_call_id": "judge_3dd81c",
  "claim_id": "claim_task_001_01_a41f82d0",
  "provider": "openai_compatible",
  "model": "configured-model",
  "prompt_version": "claim_support_v1",
  "temperature": 0,
  "cache_key": "sha256:...",
  "cache_hit": true,
  "latency_ms": 842,
  "input_tokens": 1100,
  "output_tokens": 143,
  "estimated_cost": 0.0,
  "redacted": false,
  "status": "success",
  "error": null
}
```

Raw provider responses are not persisted when they may contain sensitive or unrelated content. Validated verdict output and operational metadata are sufficient.

## 14. Reproducibility, Cost, And Privacy

- Deterministic checks run before semantic calls.
- Semantic judgment is optional and explicitly configured.
- Temperature is fixed at zero.
- A fixed seed is used where supported.
- Cache keys include claim, evidence, provider, model, prompt version, and schema version.
- Cache entries are invalidated when any keyed input changes.
- Evidence items and total evidence characters are bounded.
- Per-run call and cost budgets are configurable.
- Budget exhaustion marks unresolved claims for review.
- External calls pass through a configurable redaction hook.
- Credentials, environment variables, and hidden prompts never enter judge context.
- Repeat agreement is measured during calibration.

## 15. Severity Policy

The semantic judge may identify claim type and assertion mode, but final severity is calculated by deterministic policy.

### Risk Levels

- `low`
- `medium`
- `high`

Every claim receives a potential risk level based on claim type and task domain. A problematic verdict exposes that risk as issue severity; a supported claim has `severity=none` but retains its risk weight for scoring.

### Default Policy

| Situation | Default Risk Or Severity |
| --- | --- |
| Invented number, date, approval, churn status, contract status, or business event | High |
| Claim contradicted by structured evidence | High |
| Cross-entity evidence mismatch | High |
| Unsupported causal explanation or recommendation rationale | Medium |
| Partially supported number, scope, or qualifier | Medium |
| Weak attribution or minor descriptive overstatement | Low |
| Properly caveated insufficient-evidence statement | None |

Benchmarks may configure domain risk tags and narrow policy overrides. They should not need to enumerate every forbidden phrase.

## 16. Scoring And Status

### Base Verdict Values

| Verdict | Value |
| --- | ---: |
| `supported` | 1.0 |
| `partially_supported` | 0.5 |
| `unsupported` | 0.0 |
| `contradicted` | 0.0 |
| `not_enough_evidence`, asserted | 0.0 |
| Properly supported evidence-insufficiency caveat | 1.0 or not applicable |

### Risk Weights

```text
low     = 1
medium  = 2
high    = 4
```

### Claim-Faithfulness Score

```text
sum(verdict value * claim risk weight)
---------------------------------------
sum(claim risk weights)
```

### Hard Gates

- Any high-severity `unsupported` claim fails the task.
- Any high-severity `contradicted` claim fails the task.
- Any confidently asserted high-risk claim with `not_enough_evidence` fails the task.
- Provider infrastructure failure produces `needs_review` when it blocks a required verdict.
- Invalid claim, evidence, or verdict schema produces `needs_review`.
- No factual claims makes faithfulness `not_applicable`, not automatically perfect.

Task statuses are:

- `pass`
- `fail`
- `needs_review`

The overall numeric threshold remains `0.80`, but hard claim gates take precedence. Run summaries must report `needs_review` separately from failures.

## 17. Runtime Transition

v1.3 replaces the legacy regex-derived faithfulness scorer in the active scoring path.

- Trace schema `1.0` remains valid.
- Existing v1.2 traces can be rescored with the v1.3 evaluator.
- Existing v1.2 generated reports are historical artifacts, not runtime compatibility requirements.
- The v1.2 commit, release tag, and changelog preserve prior behavior.
- No permanent `legacy`, `compare`, or `off` faithfulness modes are added.
- One curated migration comparison may demonstrate why v1.3 differs from v1.2.

When no semantic provider is configured, deterministic evaluation still runs. Semantically unresolved medium- or high-risk claims become `needs_review`; they are not optimistically scored as supported.

## 18. Run Artifacts

Each v1.3 run adds:

- `claims.jsonl`
- `evidence.jsonl`
- `claim_verdicts.jsonl`
- `judge_calls.jsonl`
- `annotations.jsonl`
- `claim_metrics.json`
- `calibration_report.json`, when calibration is run

Stable identifiers:

- `run_id`
- `task_id`
- `claim_id`
- `evidence_id`
- `judge_call_id`
- `annotation_id`

Human annotations never overwrite machine verdicts. Gold labels are generated from adjudicated annotations.

## 19. Calibration Dataset

The v1.3 calibration dataset contains approximately 100 claim-evidence cases:

| Source | Target Cases |
| --- | ---: |
| Customer-risk agent traces | 30 |
| PCA SQL, RAG, and hybrid traces | 20 |
| Adversarial mutations | 40 |
| Tool failure and insufficient-evidence cases | 10 |

Required adversarial coverage:

- Invented or altered numbers.
- Entity swaps.
- Unsupported customer or company status.
- Negation and caveated language.
- Causal overreach.
- Policy and approval claims.
- Correct paraphrases.
- Partial support.
- Explicit contradictions.
- Empty retrieval and failed SQL.
- Cross-source synthesis.

### Splits

```text
60 development
20 calibration
20 held-out test
```

Held-out labels are excluded from prompt iteration. They may be published after the release evaluation is frozen.

## 20. Human Labeling And Gold Creation

Workflow:

```text
dataset generation
  -> proposed labels
  -> primary reviewer verifies all 100
  -> second reviewer independently labels 20 held-out cases
  -> disagreements are adjudicated
  -> adjudicated labels become gold
```

Rules:

- Proposed labels are never called gold before human review.
- Reviewers do not see the machine judge verdict while labeling.
- Overrides require a rationale.
- Reviewer identity may be a stable pseudonymous ID.
- Inter-reviewer agreement is calculated only on independently labeled cases.
- If a second reviewer is unavailable, the release must disclose the single-reviewer limitation and omit agreement claims.

## 21. Calibration Metrics

| Component | Required Metrics |
| --- | --- |
| Claim extraction | Precision, recall, F1, atomicity error rate |
| Verdict classification | Macro F1, per-verdict precision, recall, F1, confusion matrix |
| Unsupported claims | Precision, recall, F1 |
| Evidence attribution | Evidence-reference precision, recall, F1 |
| Severity | Weighted accuracy, high-severity miss count |
| Reliability | Judge error rate, abstention rate, repeat agreement |
| Human labels | Raw agreement and Cohen's kappa |

Results must be reported separately for SQL, RAG, and hybrid cases and separately for deterministic-only versus composite judgments.

### Release Gates

```text
Claim extraction recall                  >= 0.90
Claim extraction precision               >= 0.85
Five-verdict macro F1                    >= 0.80
Unsupported + contradicted recall        >= 0.90
Evidence-reference F1                    >= 0.80
High-severity false negatives            0 on held-out set
Structured judge-output validity         >= 0.98
Human label agreement                    Cohen's kappa >= 0.75
```

Reports include raw counts and bootstrap confidence intervals. Judge errors and abstentions remain in denominators where applicable.

## 22. Streamlit Review Workflow

The dashboard adds a claim-review and calibration area for technical and less-technical reviewers.

Required views:

- Claim in original answer context.
- SQL and document evidence displayed separately.
- Machine verdict, confidence, reason, unsupported parts, and severity.
- Referenced evidence highlighting.
- Plain-language human label controls.
- Verdict, severity, evidence-reference, and rationale overrides.
- Filters for verdict, severity, task type, claim type, and review status.
- Disagreement and adjudication view.
- Calibration metrics and confusion matrix.
- JSONL annotation export.

Plain-language labels:

| Internal | Reviewer Text |
| --- | --- |
| `supported` | Fully supported |
| `partially_supported` | Only partly supported |
| `unsupported` | Evidence does not support this |
| `contradicted` | Evidence conflicts with this |
| `not_enough_evidence` | Cannot determine from available evidence |

Authentication, assignments, and hosted persistence remain out of scope.

## 23. CLI Requirements

Existing `run` and `score` commands invoke claim evaluation automatically in v1.3.

New calibration commands:

```powershell
agenteval build-calibration --out calibration/claim_faithfulness_v1
agenteval calibrate --dataset calibration/claim_faithfulness_v1 --out runs/calibration-v1
agenteval adjudicate --annotations calibration/claim_faithfulness_v1/annotations --out calibration/claim_faithfulness_v1/gold.jsonl
```

Provider configuration is external to benchmarks. Benchmarks may define domain risk policy, but they must not contain provider credentials or model secrets.

## 24. Testing And CI

Required test layers:

- Claim, evidence, verdict, judge-call, and annotation schema tests.
- Atomic extraction and compound-sentence tests.
- Negation and caveat tests.
- Evidence construction for SQL, RAG, document lookup, empty output, and tool failure.
- Candidate selection ordering and truncation tests.
- Numeric tolerance and contradiction tests.
- Entity mismatch and cross-entity tests.
- Deterministic precedence tests.
- Mock semantic provider success, invalid output, timeout, retry, and budget tests.
- Cache hit, miss, and invalidation tests.
- Severity policy tests.
- Hard-gate and `needs_review` tests.
- Artifact round-trip tests.
- Calibration metric and confusion-matrix tests.
- Annotation and adjudication tests.
- Dashboard data-loading tests.
- Existing trace validation, PCA adapter, runner, and CLI regression tests.

CI continues to cover Python 3.11 and 3.12. Semantic-provider tests use mocks and must not require network access or credentials.

## 25. Acceptance Criteria

- Package and runtime version report `1.3.0`.
- Trace schema `1.0` remains accepted without conversion.
- The legacy regex faithfulness scorer is not used in active scoring.
- Every extracted claim validates against the claim schema.
- Every evidence item is trace-derived and provenance-linked.
- Every completed verdict includes a reason and evidence references considered.
- Deterministic structured contradictions cannot be overturned by a semantic provider.
- High-risk hard gates and `needs_review` behavior are enforced.
- All required JSONL and JSON artifacts are generated deterministically.
- The 100-case dataset satisfies source, verdict, and adversarial coverage targets.
- Primary review is complete for all cases.
- Independent held-out review and adjudication are complete, or the limitation is explicitly disclosed.
- Release metrics meet every applicable gate in Section 21.
- Streamlit supports blind labeling, overrides, adjudication, and metric review.
- CI, lint, compilation, unit tests, CLI smoke tests, and calibration smoke tests pass.
- README presents calibration results without claiming production readiness.

## 26. Risks And Mitigations

### Circular Evaluation

Risk: The same model creates claims, verdicts, and gold labels.

Mitigation: Separate extractor and judge interfaces, hide gold from runtime, and require human verification before labels become gold.

### Judge Overconfidence

Risk: Semantic output appears authoritative despite weak evidence.

Mitigation: Deterministic precedence, structured output validation, confidence reporting, abstention, and `needs_review`.

### Dataset Overfitting

Risk: Prompts are tuned to a small public benchmark.

Mitigation: Protected held-out labels, adversarial diversity, source-level reporting, and explicit sample-size limitations.

### Cost And Provider Drift

Risk: Model updates or repeated calls change cost and behavior.

Mitigation: Provider metadata, prompt versioning, cache keys, budgets, repeat-agreement checks, and no hardcoded model.

### Annotation Burden

Risk: Human review delays release completion.

Mitigation: Proposed labels, focused dashboard workflow, primary review of all cases, and second review limited to held-out cases.

### Privacy Leakage

Risk: Trace evidence sent to an external judge contains sensitive content.

Mitigation: Explicit opt-in, redaction hook, bounded evidence, operational metadata, and deterministic-only operation.

## 27. Reviewer Proof Path

The v1.3 reviewer path should be:

```text
release PRD
  -> claim and evidence schemas
  -> one trace-to-verdict example
  -> calibration dataset and annotation guide
  -> held-out metrics and confusion matrix
  -> claim-review dashboard
  -> CI and reproducibility commands
```

## 28. Release Boundary

v1.3 establishes calibrated claim faithfulness. v1.4 may add calibrated completeness and synthesis evaluation, repeated-run experiments, confidence intervals across model configurations, cost and latency comparison, regression gates, and historical trend reporting.
