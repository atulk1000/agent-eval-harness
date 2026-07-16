# Public Company Research Assistant Bridge

This example implements the AgentEval bridge to the external SQL + RAG project `public-company-research-assistant`.

## Current State

The bridge accepts PCA-shaped responses containing generated SQL, SQL rows, retrieved filing chunks, the final answer, route, and planning metadata. AgentEval captures or accepts those raw responses before adapting them, so evidence provenance is retained instead of inferred from aggregate outcome flags.

## Why This Bridge Matters

The built-in AgentEval demo proves the harness locally with a fictional B2B SaaS customer-risk agent.

This bridge shows the intended external-agent path:

```text
PCA raw answer_question response
  -> AgentEval PCA adapter
  -> AgentEval trace schema
  -> imported trace scoring
  -> comparable report/dashboard
```

That makes AgentEval look like a reusable evaluation framework rather than a one-off demo.

## Bridge Implementation

The bridge includes:

- `benchmark.json`: one SQL, one RAG, and one hybrid bridge task.
- `raw_responses.jsonl`: PCA-shaped contract fixtures.
- `proof/traces.jsonl`: adapted versioned traces.
- `proof/claims.jsonl`, `evidence.jsonl`, `claim_verdicts.jsonl`, and report artifacts: v1.3 scored proof.
- `agenteval/adapters/public_company.py`: offline response adapter and capture launcher.
- `agenteval/adapters/pca_capture_worker.py`: standalone worker that runs in PCA's environment.

Adapt and score the checked-in contract fixtures:

```powershell
python -m agenteval.cli adapt-pca --responses examples/public_company_research_assistant/raw_responses.jsonl --benchmark examples/public_company_research_assistant/benchmark.json --out-trace runs/pca/traces.jsonl
python -m agenteval.cli validate --trace runs/pca/traces.jsonl
python -m agenteval.cli score --trace runs/pca/traces.jsonl --benchmark examples/public_company_research_assistant/benchmark.json --agent-name public_company_research_assistant --out runs/pca-scored
```

Capture fresh responses using PCA's own Python environment:

```powershell
python -m agenteval.cli capture-pca --pca-repo ../public-company-research-assistant --pca-python ../public-company-research-assistant/.venv/Scripts/python.exe --benchmark examples/public_company_research_assistant/benchmark.json --out-responses runs/pca/raw_responses.jsonl
```

## Honesty Boundary

The checked-in responses are explicitly marked `contract_fixture`. The v1.3 result is one pass, one fail, and one `needs_review`, with two supported, two partially supported, and one unresolved claim. The unresolved and partial results expose ticker-to-company alias and semantic synthesis evidence that the portable trace does not establish by itself. This is not a fresh measurement of PCA's live quality.

The adapter never converts `sql_present=true` or `retrieval_present=true` summary flags into evidence. Summary-only inputs fail with a message requesting raw PCA responses.
