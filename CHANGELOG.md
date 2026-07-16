# Changelog

All notable changes to AgentEval Harness are documented here.

## 1.3.0 - 2026-07-15

### Added

- Atomic deterministic claim extraction with an optional cached semantic extractor.
- Trace-only SQL, document, empty-result, and tool-error evidence records.
- Five-verdict deterministic-first claim judge with optional OpenAI-compatible escalation.
- Deterministic severity policy, risk-weighted scoring, hard gates, and `needs_review` status.
- Versioned claim, evidence, verdict, judge-call, and annotation JSON Schemas.
- Per-run claim artifacts and claim-aware Markdown reports.
- Reproducible 100-case proposed calibration dataset and release-gate metrics.
- Human annotation, independent review, adjudication, agreement, and JSONL export workflows.
- Streamlit claim review with blind calibration mode and separate SQL/document evidence.
- `build-calibration`, `calibrate`, and `adjudicate` CLI commands.

### Changed

- Replaced the active regex trap-based faithfulness scorer with evidence-linked claim evaluation.
- Preserved trace schema `1.0` while aligning package/runtime version to `1.3.0`.
- Expanded automated coverage to 99 tests.

### Known Limitation

- Human gold labels and independent held-out adjudication are not yet complete. Calibration gates remain unevaluated and are not claimed as passed.

## 1.2.0 - 2026-07-15

### Added

- Versioned AgentEval trace schema `1.0` and machine-readable JSON Schema.
- Aggregated JSONL validation with legacy v1.1 normalization warnings.
- `validate`, `adapt-pca`, and `capture-pca` CLI commands.
- Public Company Research Assistant raw-response adapter and standalone capture worker.
- SQL, RAG, and hybrid PCA bridge benchmark with explicit contract fixtures.
- Golden valid, legacy, and invalid trace fixtures.
- Validation, adapter, runner, and CLI test coverage.
- Python 3.11 and 3.12 CI matrix with lint and end-to-end smoke tests.

### Changed

- External traces are validated before scoring.
- Trace recorder now emits `schema_version` and run metadata.
- SQL entity extraction supports company names and ticker symbols.

## 0.1.0 - 2026-07-08

- Initial hybrid SQL + RAG evaluation harness.
- Scripted baseline and improved demo agents.
- Fifteen-task customer-risk benchmark.
- Deterministic scorers, report generation, comparison, and Streamlit dashboard.
