# AgentEval Harness

[![CI](https://github.com/atulk1000/agent-eval-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/atulk1000/agent-eval-harness/actions/workflows/ci.yml)

Trace-based evaluation for hybrid SQL + RAG agents.

AgentEval evaluates observable agent behavior across tool routing, SQL correctness, retrieval grounding, claim faithfulness, and cross-source synthesis. Version 1.3.0 replaces regex trap scoring with atomic claims, trace-only evidence, deterministic-first verdicts, optional semantic escalation, risk-weighted hard gates, and human calibration workflows.

See the [product PRD](docs/prd_agent_eval_harness.md), [v1.3 release PRD](docs/prd_v1_3_calibrated_claim_faithfulness.md), and [implementation record](docs/v1_3_implementation_plan.md).

The v1.3 software path and proposed 100-case dataset are implemented. Human gold creation is intentionally incomplete, so the checked-in calibration report remains `pending_human_review` and no release-gate result is claimed.

## Reviewer Path

To review this project quickly:

1. Start with [docs/prd_agent_eval_harness.md](docs/prd_agent_eval_harness.md) for the product scope.
2. Inspect [benchmarks/customer_risk.yaml](benchmarks/customer_risk.yaml) for trace-aware benchmark tasks.
3. Review [agenteval/claim_eval/](agenteval/claim_eval/) and [schemas/](schemas/) for claim, evidence, verdict, judge-call, annotation, and trace contracts.
4. Inspect the [proposed calibration dataset](calibration/claim_faithfulness_v1/) and its pending report.
5. Inspect the implemented [Public Company Research Assistant bridge](examples/public_company_research_assistant/) for external-agent proof.
6. Run the scripted agents, import an external trace, or launch Streamlit for blind claim review.

## What It Tests

- Did the agent choose SQL, RAG, or both correctly?
- Did SQL execute safely and return the expected entities?
- Did retrieval find the expected documents?
- Did the final answer stay grounded in the trace?
- Which claims were unsupported or overconfident?
- Which agent configuration performed better?

## Sample Results

The bundled benchmark has 15 tasks: 5 SQL-only, 5 RAG-only, and 5 hybrid SQL + RAG.

| Agent | Overall | Passed | Failed | Claim Issues | High Severity |
| --- | ---: | ---: | ---: | ---: | ---: |
| `baseline_agent` | 0.848 | 10 | 5 | 6 | 3 |
| `improved_agent` | 0.966 | 15 | 0 | 1 | 0 |

The baseline and improved agents are scripted benchmark fixtures. They make the scorer behavior reproducible; their results are not presented as model-generalization measurements. The baseline intentionally overclaims and skips evidence, while the improved fixture follows the desired trace policy.

Curated sample artifacts:

- [baseline_summary.json](examples/sample_runs/baseline_summary.json)
- [improved_summary.json](examples/sample_runs/improved_summary.json)
- [comparison.json](examples/sample_runs/comparison.json)
- [unsupported_claims.json](examples/sample_runs/unsupported_claims.json)

## Independent Agent Proof

The v1.2 PCA bridge converts raw responses from the separate `public-company-research-assistant` repository into the same versioned trace contract. It maps only evidence that PCA actually returns:

- Generated SQL and result rows become `sql_query` events.
- Retrieved filing chunks become `rag_search` events.
- Route, status, planning, source revision, and final answer remain inspectable metadata.
- Summary-only booleans are rejected because they cannot establish evidence provenance.

The checked-in fixture covers one SQL, one RAG, and one hybrid task. Rescoring it with v1.3 yields one pass, one fail, and one `needs_review`: two claims are supported, two are partial, and one requires semantic review. This deliberately exposes alias and evidence-capture gaps that the v1.2 aggregate score hid. It proves the adapter and governance path, not current live PCA quality. See [the proof artifacts](examples/public_company_research_assistant/proof/) and [bridge documentation](examples/public_company_research_assistant/README.md).

## Unsupported Claim Example

AgentEval makes unsupported claims explicit instead of burying them in a single final-answer score.

```json
{
  "claim_id": "claim_hybrid_discount_candidates_evide_02_5a7efcb8",
  "claim": "Approved discounts can be offered.",
  "verdict": "not_enough_evidence",
  "severity": "high",
  "reason": "The trace does not contain the source type required to evaluate this claim.",
  "evidence_refs": ["evidence_c781c48dceb3", "evidence_aaf26c990a44"]
}
```

That asserted approval claim hard-fails because the agent skipped the policy evidence needed to establish it. `not_enough_evidence` is an abstention, not a pass.

## Quick Start

The core harness uses only the Python standard library.

```powershell
python -m agenteval.cli run benchmarks/customer_risk.yaml --agent baseline_agent --out runs/baseline
python -m agenteval.cli run benchmarks/customer_risk.yaml --agent improved_agent --out runs/improved
python -m agenteval.cli compare runs/baseline runs/improved --out runs/comparison
```

Validate a trace before scoring:

```powershell
python -m agenteval.cli validate --trace runs/improved/traces.jsonl
```

Run tests:

```powershell
python -m unittest discover -s tests
```

Optional dashboard:

```powershell
pip install -e .[dashboard]
streamlit run agenteval/dashboard/app.py
```

## Run Artifacts

Each run writes:

- `traces.jsonl`
- `scores.json`
- `summary.json`
- `unsupported_claims.json`
- `claims.jsonl`
- `evidence.jsonl`
- `claim_verdicts.jsonl`
- `judge_calls.jsonl`
- `annotations.jsonl`
- `claim_metrics.json`
- `report.md`

Generated local run directories are ignored by Git. Use the Quick Start commands to regenerate them, or inspect the compact checked-in examples under [examples/sample_runs/](examples/sample_runs/).

## External Trace Import

AgentEval can score traces from external agents if they emit the expected JSONL run schema:

```powershell
python -m agenteval.cli score --trace runs/improved/traces.jsonl --benchmark benchmarks/customer_risk.yaml --agent-name imported_improved --out runs/imported_improved
```

Rows without `schema_version` are accepted as legacy v1.1 traces with a warning. Use `--strict-version` to require schema `1.0` explicitly. Malformed rows, duplicate task IDs, invalid event ordering, and unknown benchmark tasks are rejected before scoring.

Optional semantic extraction and judgment use external CLI configuration, never benchmark credentials:

```powershell
$env:AGENTEVAL_JUDGE_API_KEY = "..."
python -m agenteval.cli score --trace runs/external/traces.jsonl --benchmark benchmarks/customer_risk.yaml --judge-provider openai-compatible --judge-model configured-model --judge-endpoint https://provider.example/v1 --judge-cache runs/judge-cache.json
```

Adapt raw PCA responses offline:

```powershell
python -m agenteval.cli adapt-pca --responses examples/public_company_research_assistant/raw_responses.jsonl --benchmark examples/public_company_research_assistant/benchmark.json --out-trace runs/pca/traces.jsonl
python -m agenteval.cli score --trace runs/pca/traces.jsonl --benchmark examples/public_company_research_assistant/benchmark.json --agent-name public_company_research_assistant --out runs/pca-scored
```

## Calibration Workflow

The checked-in dataset contains 30 customer-risk cases, 20 PCA cases, 40 adversarial mutations, and 10 tool-failure cases. Splits are 60 development, 20 calibration, and 20 held out.

```powershell
python -m agenteval.cli build-calibration --out calibration/claim_faithfulness_v1
python -m agenteval.cli adjudicate --annotations calibration/claim_faithfulness_v1/annotations --out calibration/claim_faithfulness_v1/gold.jsonl
python -m agenteval.cli calibrate --dataset calibration/claim_faithfulness_v1 --out calibration/claim_faithfulness_v1
```

`build-calibration` refuses to overwrite human annotations or gold. Primary review is required for all cases; the held-out split requires a second independent reviewer or adjudication. Streamlit keeps machine proposals hidden by default during calibration review and exports human annotations as JSONL.

## Project Layout

```text
agenteval/      Runner, trace validation, claim evaluation, adapters, reports, dashboard
agents/         Baseline and improved demo agents
benchmarks/     Trace-aware benchmark suite
calibration/    Proposed cases, machine proposals, annotations, and pending metrics
data/           Generated SQLite database and document corpus
docs/           Product and release PRDs
examples/       Curated built-in and external-agent proof artifacts
runs/           Local run artifacts
schemas/        Machine-readable trace and claim-evaluation contracts
tests/          Unit tests
```
