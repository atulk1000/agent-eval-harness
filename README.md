# AgentEval Harness

[![CI](https://github.com/atulk1000/agent-eval-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/atulk1000/agent-eval-harness/actions/workflows/ci.yml)

Trace-based evaluation for hybrid SQL + RAG agents.

AgentEval evaluates observable agent behavior across tool routing, SQL correctness, retrieval grounding, unsupported claims, and cross-source synthesis. The MVP uses a fictional B2B SaaS customer intelligence domain and includes a demo hybrid agent, benchmark tasks, scoring artifacts, external trace import, and a Streamlit dashboard.

See [docs/prd_agent_eval_harness.md](docs/prd_agent_eval_harness.md) for the PRD and implementation plan.

## Reviewer Path

To review this project quickly:

1. Start with [docs/prd_agent_eval_harness.md](docs/prd_agent_eval_harness.md) for the product scope.
2. Inspect [benchmarks/customer_risk.yaml](benchmarks/customer_risk.yaml) for trace-aware benchmark tasks.
3. Review [agenteval/trace.py](agenteval/trace.py) for the observable trace schema.
4. Review [agenteval/scorers/](agenteval/scorers/) for tool routing, SQL, retrieval, facts, efficiency, and judge-style scoring.
5. Run baseline vs improved agents using the Quick Start commands.
6. Inspect [examples/sample_runs/](examples/sample_runs/) or launch the Streamlit dashboard to review failures.

## What It Tests

- Did the agent choose SQL, RAG, or both correctly?
- Did SQL execute safely and return the expected entities?
- Did retrieval find the expected documents?
- Did the final answer stay grounded in the trace?
- Which claims were unsupported or overconfident?
- Which agent configuration performed better?

## Sample Results

The bundled benchmark has 15 tasks: 5 SQL-only, 5 RAG-only, and 5 hybrid SQL + RAG.

| Agent | Overall | Passed | Failed | Unsupported Claims | High Severity |
| --- | ---: | ---: | ---: | ---: | ---: |
| `baseline_agent` | 0.859 | 10 | 5 | 4 | 4 |
| `improved_agent` | 0.970 | 15 | 0 | 0 | 0 |

The baseline agent intentionally makes realistic mistakes such as overclaiming churn, approving discounts without evidence, and skipping required RAG context. The improved agent uses the same four tools but routes, grounds, and caveats its answers more carefully.

Curated sample artifacts:

- [baseline_summary.json](examples/sample_runs/baseline_summary.json)
- [improved_summary.json](examples/sample_runs/improved_summary.json)
- [comparison.json](examples/sample_runs/comparison.json)
- [unsupported_claims.json](examples/sample_runs/unsupported_claims.json)

## Unsupported Claim Example

AgentEval makes unsupported claims explicit instead of burying them in a single final-answer score.

```json
{
  "task_id": "hybrid_discount_candidates_evidence",
  "claim": "Discounts were already approved",
  "verdict": "unsupported",
  "severity": "high",
  "reason": "The policy states requirements before approval; no trace evidence says a discount was approved.",
  "evidence_refs": []
}
```

That claim is high severity because the trace supports discount approval requirements, not an approved discount.

## Quick Start

The core harness uses only the Python standard library.

```powershell
python -m agenteval.cli run benchmarks/customer_risk.yaml --agent baseline_agent --out runs/baseline
python -m agenteval.cli run benchmarks/customer_risk.yaml --agent improved_agent --out runs/improved
python -m agenteval.cli compare runs/baseline runs/improved --out runs/comparison
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
- `report.md`

Generated local run directories are ignored by Git. Use the Quick Start commands to regenerate them, or inspect the compact checked-in examples under [examples/sample_runs/](examples/sample_runs/).

## External Trace Import

AgentEval can score traces from external agents if they emit the expected JSONL run schema:

```powershell
python -m agenteval.cli score --trace runs/improved/traces.jsonl --benchmark benchmarks/customer_risk.yaml --agent-name imported_improved --out runs/imported_improved
```

The bridge plan for connecting this harness to the separate Public Company Research Assistant repo lives in [examples/public_company_research_assistant/](examples/public_company_research_assistant/). That project already has SQL/RAG/hybrid eval outputs; v1.1 documents the honest adapter boundary for converting those outputs into AgentEval traces.

## Project Layout

```text
agenteval/      Core runner, tools, trace schema, scorers, reports, dashboard
agents/         Baseline and improved demo agents
benchmarks/     Trace-aware benchmark suite
data/           Generated SQLite database and document corpus
docs/           PRD and implementation plan
examples/       Curated proof artifacts and external integration notes
runs/           Local run artifacts
tests/          Unit tests
```
