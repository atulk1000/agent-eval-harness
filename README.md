# AgentEval Harness

Trace-based evaluation for hybrid SQL + RAG agents.

AgentEval evaluates observable agent behavior across tool routing, SQL correctness, retrieval grounding, unsupported claims, and cross-source synthesis. The MVP uses a fictional B2B SaaS customer intelligence domain and includes a demo hybrid agent, benchmark tasks, scoring artifacts, external trace import, and a Streamlit dashboard.

See [docs/prd_agent_eval_harness.md](docs/prd_agent_eval_harness.md) for the PRD and implementation plan.

## What It Tests

- Did the agent choose SQL, RAG, or both correctly?
- Did SQL execute safely and return the expected entities?
- Did retrieval find the expected documents?
- Did the final answer stay grounded in the trace?
- Which claims were unsupported or overconfident?
- Which agent configuration performed better?

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

## Project Layout

```text
agenteval/      Core runner, tools, trace schema, scorers, reports, dashboard
agents/         Baseline and improved demo agents
benchmarks/     Trace-aware benchmark suite
data/           Generated SQLite database and document corpus
docs/           PRD and implementation plan
runs/           Local run artifacts
tests/          Unit tests
```
