# AgentEval Harness v1.2

## Independent Proof Release PRD

Status: Implemented in v1.2.0; historical release contract

Release: v1.2

Package version: 1.2.0

Theme: Evaluate an agent the harness did not create

## 1. Release Summary

AgentEval v1.2 turns the v1.1 demonstration into a reusable evaluation contract. The release adds a versioned trace schema, strict validation, safer external trace import, and a real adapter for raw responses from the separate Public Company Research Assistant (PCA) project.

The release keeps the core standard-library-only. Optional integrations may depend on the external agent's own environment, but imported traces must remain portable JSONL.

## 2. Problem

v1.1 proves the end-to-end evaluation workflow, but its strongest results come from demo agents that are aware of benchmark task IDs. External traces can be scored, but they are not validated against a formal schema. The PCA bridge documents a mapping but does not implement it.

This leaves three reviewer questions unanswered:

1. Can malformed or incomplete external traces be rejected clearly?
2. Can the harness evaluate a hybrid agent from another repository?
3. Can the proof avoid inventing evidence that the external system did not emit?

## 3. Goals

- Define a versioned, machine-readable trace contract.
- Validate trace files before scoring and report all actionable errors.
- Keep backward compatibility with valid v1.1 traces.
- Add a CLI command for validation.
- Add an adapter for raw PCA responses containing SQL rows and retrieved documents.
- Add a capture path that runs selected PCA benchmark prompts when the PCA environment is available.
- Check in a truthful SQL, RAG, and hybrid PCA contract fixture and scored proof artifacts.
- Expand tests across validation, import, adapters, runners, and scorer edge cases.
- Strengthen CI with a Python version matrix, lint checks, and an end-to-end CLI smoke test.
- Align package and release versioning.

## 4. Non-Goals

- Hosted evaluation service.
- Authentication or team workspaces.
- General adapters for every agent framework.
- Arbitrary MCP server evaluation.
- Model-backed semantic judging; this remains a v1.3 objective.
- Treating PCA summary booleans as fabricated SQL rows or retrieved chunks.
- Modifying hidden chain-of-thought or requiring it in traces.

## 5. Trace Contract

Every JSONL row represents one completed task run.

Required run fields:

- `schema_version`
- `run_id`
- `task_id`
- `agent_name`
- `model`
- `started_at`
- `completed_at`
- `final_answer`
- `trace`

Required tool-event fields:

- `step`
- `type=tool_call`
- `tool`
- `input`
- `output`
- `success`
- `error`
- `latency_ms`

Optional run metadata may include source repository, source revision, adapter name, route, planner configuration, and evaluation notes. Unknown metadata is preserved.

The current schema version is `1.0`. Valid v1.1 rows without `schema_version` are normalized to `1.0` during import and receive a compatibility warning.

## 6. Validation Rules

- Required fields must exist and have the expected primitive type.
- `trace` must be a list of tool events.
- Tool event steps must be positive, unique, and strictly increasing.
- Tool names must be non-empty strings.
- `success=false` requires a non-empty error.
- `latency_ms` must be a non-negative integer.
- SQL output rows and RAG output documents must be lists when present.
- Each task ID may appear only once in an imported trace file.
- Imported task IDs must exist in the benchmark before scoring.
- Unsupported future schema versions must fail with a clear message.

The validator returns every discovered issue rather than stopping at the first malformed field.

## 7. CLI

Validate without scoring:

```powershell
python -m agenteval.cli validate --trace path/to/traces.jsonl
```

Adapt captured PCA raw responses:

```powershell
python -m agenteval.cli adapt-pca \
  --responses path/to/pca_responses.jsonl \
  --benchmark examples/public_company_research_assistant/benchmark.json \
  --out-trace runs/pca/traces.jsonl
```

Capture selected PCA prompts using the sibling repository:

```powershell
python -m agenteval.cli capture-pca \
  --pca-repo ../public-company-research-assistant \
  --benchmark examples/public_company_research_assistant/benchmark.json \
  --out-responses runs/pca/raw_responses.jsonl
```

Capture must call the public PCA `answer_question` function with `return_trace=true`. It may fail with an environment-specific message if PCA dependencies or backing services are unavailable; adaptation and scoring remain offline.

## 8. PCA Mapping

| PCA response | AgentEval |
| --- | --- |
| response route | `metadata.route` |
| `structured_evidence.sql` | `sql_query.input.query` |
| `structured_evidence.rows` | `sql_query.output.rows` |
| retrieved item metadata | `rag_search.output.documents[*]` |
| response answer | `final_answer` |
| planning or `agent_trace` | run `metadata` |

The adapter creates only events supported by actual response content. A route of `sql`, `rag`, or `hybrid` does not by itself create a tool event.

Summary-only PCA reports are not sufficient input because they contain booleans instead of evidence payloads.

## 9. Independent Proof Suite

The checked-in PCA bridge benchmark contains:

- One SQL task.
- One RAG task.
- One hybrid task.
- Route expectations and evidence-shape expectations.
- No expected answer phrases copied from the agent output.

Checked-in raw responses are explicitly labeled contract fixtures. They verify the adapter and scoring contract, not current live PCA quality. A live capture can replace them without changing the benchmark or scorers.

## 10. Testing And CI

Required tests:

- Valid trace acceptance.
- Legacy trace normalization.
- Missing run fields.
- Invalid event ordering and types.
- Failed event without an error.
- Duplicate task IDs.
- Unknown benchmark task IDs.
- SQL, RAG, and hybrid PCA mapping.
- Summary-only PCA input rejection.
- CLI validation success and failure.
- End-to-end imported trace scoring.
- Existing benchmark and demo-agent regression tests.

CI must run on Python 3.11 and 3.12 and include:

- Compilation.
- Unit tests.
- `ruff` linting.
- Baseline and improved CLI smoke runs.
- External trace validation and scoring smoke test.

## 11. Acceptance Criteria

- `validate` exits zero for valid traces and non-zero with actionable messages for invalid traces.
- Existing v1.1 traces continue to score through compatibility normalization.
- The PCA adapter maps actual SQL rows and retrieved chunks without fabricated evidence.
- One SQL, one RAG, and one hybrid PCA fixture score end to end.
- At least 20 focused unit tests pass.
- CI covers Python 3.11 and 3.12.
- README shows the independent proof workflow and its honesty boundary.
- Package version and `agenteval.__version__` both report `1.2.0`.

## 12. Release Boundary

v1.2 establishes transport, validation, and independent-agent proof. v1.3 will improve semantic evaluation validity through claim extraction, evidence-linked verdicts, a judge-provider interface, and calibration metrics.
