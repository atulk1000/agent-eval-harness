# AgentEval Harness v1.3 Implementation Plan

Status: Software implemented; human review and adjudication pending

Release PRD: [prd_v1_3_calibrated_claim_faithfulness.md](prd_v1_3_calibrated_claim_faithfulness.md)

Target package version: 1.3.0

## 1. Objective

Implement a calibrated, evidence-linked claim-faithfulness evaluator that replaces the legacy regex scorer while preserving AgentEval trace schema `1.0` compatibility.

The implementation is complete only when the software path is verified and the agreed human-review gate is either completed or explicitly reported as incomplete. Generated or AI-proposed labels must not be presented as adjudicated gold.

### Implementation Outcome

Completed in the repository:

- Versioned records and published JSON Schemas.
- Deterministic plus optional semantic extraction and judgment.
- Trace-only evidence construction, selection, severity, scoring, and hard gates.
- Runtime integration and all required run artifacts.
- Reproducible 100-case proposed dataset with the approved source mix and splits.
- Blind Streamlit review, JSONL annotations, adjudication, agreement, metrics, and CI smoke paths.
- 99 automated tests across Python contracts, failures, providers, artifacts, CLI, and runners.

Outstanding release gate:

- A primary human reviewer must label all 100 cases.
- A second reviewer must independently label the 20 held-out cases.
- Disagreements must be adjudicated before calibration thresholds can be evaluated.

## 2. Delivery Strategy

Build in dependency order:

```text
v1.2 release checkpoint
  -> schemas and IDs
  -> extraction and evidence
  -> deterministic judgment
  -> semantic provider and cache
  -> scoring and artifacts
  -> calibration dataset
  -> human review and adjudication
  -> metrics and dashboard
  -> release verification
```

Rules for implementation:

- Keep trace schema `1.0` unchanged unless a genuine trace-contract defect is discovered.
- Do not retain the legacy faithfulness scorer in the active path.
- Keep semantic-provider access optional and absent from CI.
- Use deterministic mocks for all automated semantic-provider tests.
- Create artifact schemas before writing artifact producers.
- Keep proposed, machine, human, and gold labels physically distinguishable.
- Do not declare calibration acceptance until held-out evaluation is frozen.

## 3. Proposed Package Layout

```text
agenteval/
  claim_eval/
    __init__.py
    models.py
    ids.py
    extraction.py
    evidence.py
    selection.py
    deterministic.py
    providers.py
    composite.py
    severity.py
    scoring.py
    artifacts.py
    cache.py
    calibration.py
    annotations.py
    metrics.py

schemas/
  claim_v1.schema.json
  evidence_v1.schema.json
  claim_verdict_v1.schema.json
  judge_call_v1.schema.json
  annotation_v1.schema.json
  calibration_case_v1.schema.json

calibration/
  claim_faithfulness_v1/
    README.md
    annotation_guide.md
    cases.jsonl
    proposed_labels.jsonl
    annotations/
      reviewer_primary.jsonl
      reviewer_held_out.jsonl
    gold.jsonl
    metrics.json
    report.md

tests/
  fixtures/
    claim_eval/
  test_claim_models.py
  test_claim_extraction.py
  test_evidence_builder.py
  test_evidence_selection.py
  test_deterministic_claim_judge.py
  test_semantic_provider.py
  test_composite_claim_judge.py
  test_severity_policy.py
  test_claim_scoring.py
  test_claim_artifacts.py
  test_claim_cache.py
  test_calibration.py
  test_annotations.py
  test_claim_metrics.py
```

This package is intentionally cohesive. Avoid splitting provider implementations or policy tables into more modules until complexity requires it.

## 4. Phase 0: Capture The v1.2 Baseline

### Purpose

Create a clean historical boundary before replacing faithfulness behavior.

### Work

1. Review the existing v1.2 worktree diff.
2. Re-run v1.2 lint, compilation, tests, and CLI smoke workflows.
3. Confirm package version `1.2.0` and proof artifact values.
4. Commit v1.2 separately from all v1.3 work.
5. Tag the release `v1.2.0` when authorized.
6. Push and verify GitHub Actions when authorized.

### Acceptance

- v1.2 exists as an independently reviewable commit.
- v1.3 does not need runtime branches to reproduce v1.2.
- The changelog points reviewers to the release boundary.

### Effort

Half day, excluding any remote authorization delay.

## 5. Phase 1: Schemas, Models, And Stable IDs

### Purpose

Freeze the contracts every later phase consumes.

### Add

- `agenteval/claim_eval/models.py`
- `agenteval/claim_eval/ids.py`
- Six JSON Schema files under `schemas/`
- `tests/test_claim_models.py`

### Implement

Typed standard-library models or dataclasses for:

- `AtomicClaim`
- `EvidenceItem`
- `ClaimVerdict`
- `JudgeCall`
- `HumanAnnotation`
- `CalibrationCase`
- `ClaimEvaluationResult`

Required behavior:

- JSON serialization and parsing.
- Aggregated validation errors consistent with trace validation.
- Supported schema-version checks.
- Deterministic ID generation from stable inputs.
- Unknown metadata preservation.
- Strict enum validation for claim type, assertion mode, verdict, risk, and severity.

### Test Cases

- Valid round trips.
- Missing and invalid fields.
- Unknown schema versions.
- Stable IDs across repeated runs.
- ID changes when normalized claim text or evidence source changes.
- Invalid evidence references.
- Confidence outside `[0, 1]`.

### Acceptance

- All schemas are machine-readable and mirrored by runtime validation.
- The same input produces the same IDs on Python 3.11 and 3.12.
- No later phase defines ad hoc claim or evidence dictionaries.

### Effort

One day.

## 6. Phase 2: Claim Extraction And Evidence Construction

### Purpose

Produce trustworthy intermediate artifacts before judgment.

### Add

- `agenteval/claim_eval/extraction.py`
- `agenteval/claim_eval/evidence.py`
- `agenteval/claim_eval/selection.py`
- Extraction and evidence fixtures.
- `tests/test_claim_extraction.py`
- `tests/test_evidence_builder.py`
- `tests/test_evidence_selection.py`

### Claim Extraction Work

- Normalize Markdown without losing source spans.
- Split candidate sentences and clauses.
- Exclude headings, commands, greetings, and purely stylistic text.
- Detect assertion mode.
- Implement conservative deterministic extraction.
- Define semantic extractor protocol without provider coupling.
- Validate and deduplicate semantic output.
- Persist extraction warnings instead of dropping ambiguous content.

### Evidence Work

- Convert SQL rows to stable `sql_row` evidence.
- Convert RAG results to `document_chunk` evidence.
- Convert document lookups to `opened_document` evidence.
- Represent tool failures and empty results explicitly.
- Preserve event step, document ID, row index, and source metadata.
- Produce normalized text plus structured payload.

### Candidate Selection Work

- Rank exact entity, number, date, and status matches first.
- Enforce source requirements.
- Apply lexical overlap only after exact checks.
- Balance SQL and document sources for hybrid claims.
- Default to at most eight evidence items.
- Record candidate and excluded counts.
- Keep ordering deterministic.

### Test Cases

- Compound claims split into independent propositions.
- Negation and caveat preservation.
- Citation labels do not become claims.
- Numeric and entity claims retain source spans.
- SQL, RAG, opened document, error, and empty evidence.
- Cross-entity candidate exclusion.
- Exact structured match precedence.
- Candidate truncation is visible and stable.

### Acceptance

- Built-in and PCA traces generate valid claim and evidence artifacts.
- No evidence is fetched outside the trace.
- All selected evidence references resolve.

### Effort

Two days.

## 7. Phase 3: Deterministic Judgment And Severity

### Purpose

Make the offline path useful and establish precedence before introducing a model judge.

### Add

- `agenteval/claim_eval/deterministic.py`
- `agenteval/claim_eval/severity.py`
- Policy tables or configuration fixtures.
- `tests/test_deterministic_claim_judge.py`
- `tests/test_severity_policy.py`

### Deterministic Checks

- Exact structured field support.
- Numeric equality and configurable tolerance.
- Date and status matching.
- Entity and cross-entity mismatch.
- Explicit structured contradiction.
- Missing source requirement.
- Empty result and failed tool behavior.
- Unretrieved document references.
- Supported evidence-insufficiency caveats.

Each check returns:

- Whether it is decisive.
- Verdict and confidence.
- Reason.
- Evidence references.
- Unsupported parts.
- Rule identifier.

### Severity Work

- Define risk by claim type and domain tags.
- Map problematic verdicts to severity.
- Separate potential risk from issue severity.
- Support narrow benchmark policy overrides.
- Ensure the semantic provider cannot assign final severity.

### Acceptance

- Every deterministic decision is explainable by a stable rule ID.
- Structured contradictions cannot be overridden later.
- High-risk business status, approval, policy, and numeric failures receive expected severity.

### Effort

Two days.

## 8. Phase 4: Semantic Provider, Composite Judge, And Cache

### Purpose

Handle semantic cases without making the project provider-dependent.

### Add

- `agenteval/claim_eval/providers.py`
- `agenteval/claim_eval/composite.py`
- `agenteval/claim_eval/cache.py`
- Versioned prompt templates or prompt constants.
- `tests/test_semantic_provider.py`
- `tests/test_composite_claim_judge.py`
- `tests/test_claim_cache.py`

### Provider Interface

Implement:

- `RuleOnlyJudgeProvider`
- `MockJudgeProvider`
- `OpenAICompatibleJudgeProvider`

The exact external API and SDK usage must be checked against current official provider documentation during implementation. No model name is hardcoded.

### Composite Behavior

1. Run deterministic checks.
2. Return immediately for decisive structured results.
3. Build bounded semantic context for unresolved claims.
4. Call the configured provider.
5. Validate structured output.
6. Apply deterministic precedence.
7. Apply severity policy.
8. Persist sanitized call metadata.

### Cache Work

- Hash normalized claim, selected evidence, provider, model, prompt, schema, and redaction state.
- Support cache hit, miss, and invalidation.
- Store validated output only.
- Never cache failed or structurally invalid responses as verdicts.

### Reliability Work

- Bounded timeout and retries.
- Per-run call and estimated-cost budgets.
- Redaction hook.
- Token and latency metadata.
- Provider failure to `needs_review` propagation.

### Test Cases

- Successful structured output.
- Invalid JSON or missing fields.
- Timeout and retry exhaustion.
- Cost-budget exhaustion.
- Redaction metadata.
- Cache invalidation after evidence or prompt changes.
- Semantic output cannot overturn deterministic contradiction.
- No network calls in tests.

### Acceptance

- The composite judge runs with only mocks in CI.
- Deterministic-only execution remains functional.
- Provider failure never produces `supported`.

### Effort

Two days.

## 9. Phase 5: Scoring, Runner, Reports, And Artifacts

### Purpose

Make claim faithfulness the actual product behavior rather than a sidecar experiment.

### Add

- `agenteval/claim_eval/scoring.py`
- `agenteval/claim_eval/artifacts.py`
- `tests/test_claim_scoring.py`
- `tests/test_claim_artifacts.py`

### Modify

- `agenteval/scorers/engine.py`
- `agenteval/scorers/judges.py`
- `agenteval/runner.py`
- `agenteval/reports/markdown.py`
- `agenteval/reports/compare.py`
- `agenteval/cli.py`

### Scoring Work

- Implement verdict values and risk weighting.
- Implement high-risk hard gates.
- Add `needs_review` status.
- Mark no-claim faithfulness as `not_applicable`.
- Replace legacy regex faithfulness in the final dimension score.
- Report unresolved and judge-error counts.
- Keep overall score threshold at `0.80` with hard-gate precedence.

### Artifact Work

Write:

- `claims.jsonl`
- `evidence.jsonl`
- `claim_verdicts.jsonl`
- `judge_calls.jsonl`
- `annotations.jsonl`
- `claim_metrics.json`

Artifacts must be deterministic for rule-only execution and validate before being written as complete.

### Migration Work

- Continue accepting trace schema `1.0`.
- Rescore v1.2 traces through the new evaluator.
- Remove the legacy faithfulness scorer from active execution.
- Keep at most one curated before/after migration example.
- Make older dashboards tolerate absent claim artifacts.

### Acceptance

- Built-in and PCA traces score through the claim evaluator.
- Severe unsupported or contradicted claims fail regardless of aggregate score.
- Blocked required judgments become `needs_review`.
- Run reports expose claim, evidence, verdict, severity, and judge path.

### Effort

Two days.

## 10. Phase 6: Calibration Dataset Generation

### Purpose

Create balanced evaluation cases without misrepresenting machine proposals as gold.

### Add

- `agenteval/claim_eval/calibration.py`
- `calibration/claim_faithfulness_v1/README.md`
- `calibration/claim_faithfulness_v1/annotation_guide.md`
- Case-generation configuration.
- `tests/test_calibration.py`

### Dataset Work

- Collect candidate claims from customer-risk traces.
- Collect PCA SQL, RAG, and hybrid cases.
- Generate controlled adversarial mutations.
- Generate tool-error and empty-evidence cases.
- Balance verdict, claim type, source type, and risk.
- Assign development, calibration, and held-out splits deterministically.
- Generate proposed labels with provenance.
- Mark every case `pending_review` until human verification.

### Mutation Generators

- Number replacement.
- Date replacement.
- Entity swap.
- Status escalation.
- Negation removal or insertion.
- Causal phrase insertion.
- Approval or policy overstatement.
- Source-attribution swap.
- Unsupported qualifier insertion.
- Evidence deletion for insufficient-evidence cases.

### CLI

```powershell
agenteval build-calibration --out calibration/claim_faithfulness_v1
```

### Acceptance

- Approximately 100 valid cases exist.
- Source targets are within agreed tolerance.
- All mutation labels are marked proposed.
- Held-out assignment is stable and excluded from prompt development.

### Effort

Two days, excluding human review.

## 11. Phase 7: Annotation, Adjudication, And Dashboard

### Purpose

Let less-technical reviewers create defensible labels from visible evidence.

### Add

- `agenteval/claim_eval/annotations.py`
- Annotation and adjudication tests.

### Modify

- `agenteval/dashboard/app.py`

### Dashboard Work

- Add claim review, calibration, and disagreement views.
- Show original answer context.
- Separate SQL and document evidence.
- Highlight selected and gold evidence.
- Use plain-language verdict labels.
- Support verdict, severity, and evidence overrides.
- Require rationale for overrides.
- Record reviewer ID, timestamp, and annotation version.
- Hide machine verdict during blind labeling.
- Filter by review status and case metadata.
- Export append-only reviewer JSONL.
- Add adjudication controls without overwriting source annotations.

### Human Workflow Gate

1. Primary reviewer verifies all 100 cases.
2. Second reviewer independently labels 20 held-out cases.
3. Disagreements are adjudicated.
4. Adjudicated records produce `gold.jsonl`.

This gate requires real user or reviewer participation. Codex may implement the workflow and proposed labels but must not claim the human gate is complete without actual annotations.

### CLI

```powershell
agenteval adjudicate --annotations calibration/claim_faithfulness_v1/annotations --out calibration/claim_faithfulness_v1/gold.jsonl
```

### Acceptance

- Machine and human verdicts remain separate.
- Blind labeling does not reveal machine output.
- Disagreements are reproducible from source annotation files.
- Gold generation requires adjudication status.

### Effort

Two engineering days plus reviewer time.

## 12. Phase 8: Metrics And Calibration Report

### Purpose

Turn annotations into evidence that the evaluator works.

### Add

- `agenteval/claim_eval/metrics.py`
- `tests/test_claim_metrics.py`

### Metrics Work

- Claim-extraction precision, recall, and F1.
- Atomicity error rate.
- Verdict macro and per-class metrics.
- Unsupported and contradicted precision, recall, and F1.
- Evidence-reference precision, recall, and F1.
- Severity weighted accuracy and high-risk misses.
- Judge error, abstention, and repeat-agreement rates.
- Raw human agreement and Cohen's kappa.
- SQL, RAG, and hybrid slices.
- Deterministic-only and composite slices.
- Confusion matrix.
- Bootstrap confidence intervals.

### CLI

```powershell
agenteval calibrate --dataset calibration/claim_faithfulness_v1 --out runs/calibration-v1
```

### Artifacts

- `claim_metrics.json`
- `calibration_report.json`
- `calibration_report.md`
- Machine-readable confusion matrix.

### Acceptance

- Metrics match hand-computed fixture cases.
- Errors and abstentions are not silently excluded.
- Every release gate is evaluated explicitly as pass, fail, or unavailable.
- Unavailable human-review metrics block an unqualified calibration claim.

### Effort

Two days.

## 13. Phase 9: CI, Documentation, And Release Proof

### Modify

- `.github/workflows/ci.yml`
- `pyproject.toml`
- `README.md`
- `CHANGELOG.md`
- Dashboard and report documentation.

### Dependency Strategy

- Keep core deterministic evaluation standard-library-first.
- Add semantic-provider support as an optional dependency group.
- Keep Streamlit optional.
- Add any coverage dependency only to development extras.

### CI Work

- Python 3.11 and 3.12 matrix.
- Ruff and compilation.
- Full unit suite.
- Trace and claim-schema validation.
- Rule-only built-in and PCA scoring smoke tests.
- Mock composite-judge smoke test.
- Calibration fixture smoke test.
- Package installation and `pip check`.
- No external credentials or network judge calls.

### Reviewer Proof

- One trace-to-claims-to-evidence-to-verdict walkthrough.
- One high-severity hard-gate example.
- One `needs_review` provider-failure example.
- Calibration dataset overview.
- Confusion matrix and metric table.
- Dashboard screenshot after visual verification.
- Explicit limitations section.

### Release Verification

```powershell
python -m compileall agenteval agents tests
python -m ruff check agenteval agents tests
python -m unittest discover -s tests -v
agenteval validate --trace tests/fixtures/valid_trace.jsonl
agenteval run benchmarks/customer_risk.yaml --agent baseline_agent --out runs/v1_3_baseline
agenteval score --trace examples/public_company_research_assistant/proof/traces.jsonl --benchmark examples/public_company_research_assistant/benchmark.json --agent-name public_company_research_assistant --out runs/v1_3_pca
agenteval calibrate --dataset calibration/claim_faithfulness_v1 --out runs/v1_3_calibration
python -m pip check
```

An optional real-provider smoke test requires explicit credentials and approval because it may send evidence externally and incur cost.

### Acceptance

- Package version is `1.3.0` everywhere.
- CI is green on both supported Python versions.
- Calibration gates are reported honestly.
- README distinguishes software completion from human calibration completion.

### Effort

One to two days after human review.

## 14. File-Level Change Map

| Existing File | Planned Change |
| --- | --- |
| `agenteval/scorers/judges.py` | Replace regex faithfulness with claim-evaluator integration or retire the module. |
| `agenteval/scorers/engine.py` | Use claim score, hard gates, and `needs_review`. |
| `agenteval/runner.py` | Orchestrate claim evaluation and write new artifacts. |
| `agenteval/cli.py` | Add calibration and adjudication commands. |
| `agenteval/reports/markdown.py` | Render claim-level evidence, verdicts, and review status. |
| `agenteval/reports/compare.py` | Compare claim metrics and severe-error counts. |
| `agenteval/dashboard/app.py` | Add review, annotation, adjudication, and calibration views. |
| `agenteval/schema.py` | Reuse validation patterns; do not expand trace schema unnecessarily. |
| `benchmarks/customer_risk.yaml` | Add domain risk policy only if needed; do not add provider settings. |
| `pyproject.toml` | Version `1.3.0` and optional judge dependencies. |
| `.github/workflows/ci.yml` | Add claim and calibration smoke tests. |
| `README.md` | Add calibrated proof path, metrics, and limitations. |

## 15. Test Target

The current v1.2 suite must remain green. v1.3 should add enough focused tests to cover every new contract and failure path; a practical target is at least 60 total unit and integration tests.

Priority is behavioral coverage, not test count. Required failures include:

- Missing claims.
- Compound claims not split.
- Wrong entity evidence.
- Numeric contradiction.
- Missing source type.
- Semantic provider invalid output.
- Semantic provider timeout.
- Cache poisoning attempt.
- Budget exhaustion.
- High-severity hard-gate miss.
- Human annotation overwrite attempt.
- Gold generation without adjudication.
- Metrics that accidentally drop errors.

## 16. Milestone Exit Criteria

| Milestone | Exit Signal |
| --- | --- |
| Contracts | All schemas and stable-ID tests pass. |
| Intermediate artifacts | Built-in and PCA traces produce valid claims and evidence. |
| Deterministic judge | Structured facts, contradictions, caveats, and severity pass golden tests. |
| Composite judge | Mock semantic escalation, precedence, cache, and failure behavior pass. |
| Runtime integration | `run` and `score` generate claim artifacts and enforce gates. |
| Dataset | Approximately 100 balanced cases are generated and marked pending review. |
| Human review | Primary and held-out annotations are complete and adjudicated. |
| Calibration | Metrics and confidence intervals are generated without hidden exclusions. |
| Release | Gates pass or limitations are explicitly documented; CI is green. |

## 17. Definition Of Done

v1.3 is complete when:

1. The active faithfulness score is claim-based and evidence-linked.
2. Trace schema `1.0` remains usable for built-in and external agents.
3. Deterministic judgment, optional semantic escalation, caching, budgets, and privacy controls work as specified.
4. High-risk hard gates and `needs_review` are enforced.
5. Versioned claim-evaluation artifacts are generated and validated.
6. The calibration dataset meets coverage targets.
7. Human-review status is represented truthfully.
8. Every available release metric is reported with raw counts and uncertainty.
9. Required gates pass, or any blocked human-dependent gate is explicitly disclosed.
10. CI, documentation, proof artifacts, and package version are release-ready.

## 18. Post-v1.3

Defer these items to v1.4:

- Calibrated completeness and synthesis judges.
- Repeated model and planner trials.
- Cross-run confidence intervals.
- Cost and latency comparisons across configurations.
- CI regression thresholds across historical runs.
- Trend persistence and hosted review workflows.
