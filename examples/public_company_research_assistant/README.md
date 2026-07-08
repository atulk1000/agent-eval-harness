# Public Company Research Assistant Bridge

This example documents how AgentEval Harness can connect to an external SQL + RAG project in the same portfolio: `public-company-research-assistant`.

## Current State

Public Company Research Assistant already has an evaluation layer under its `evals/` directory. It tracks routing, SQL evidence, retrieval evidence, citation coverage, company resolution, and faithfulness proxies for SEC-backed financial research questions.

Its latest checked-in evaluation summary reports:

- 25 benchmark cases
- 96% pass rate
- 95.83% routing accuracy
- 100% retrieval hit rate
- 100% citation coverage
- 100% faithfulness proxy

The current PCA evaluator does not yet emit AgentEval's full trace schema. It records case-level outcomes rather than every observable tool call as `schema_lookup`, `sql_query`, `rag_search`, or `document_lookup` events.

## Why This Bridge Matters

The built-in AgentEval demo proves the harness locally with a fictional B2B SaaS customer-risk agent.

This bridge shows the intended external-agent path:

```text
Public Company Research Assistant eval output
  -> adapter
  -> AgentEval trace schema
  -> imported trace scoring
  -> comparable report/dashboard
```

That makes AgentEval look like a reusable evaluation framework rather than a one-off demo.

## v1.1 Boundary

v1.1 documents the adapter contract and includes a real excerpt from the PCA eval report.

It does not pretend PCA already emits full AgentEval traces.

## v1.2 Target

Add a PCA trace exporter that captures:

- route decision as an agent event
- generated SQL as a `sql_query` event
- SQL rows as `sql_query.output.rows`
- retrieved filing chunks as `rag_search.output.documents`
- final answer and citations as `final_answer`
- route mismatch and citation/faithfulness outcomes as score metadata

Once that exporter exists, AgentEval can score PCA runs through:

```powershell
python -m agenteval.cli score --trace examples/public_company_research_assistant/trace.jsonl --benchmark examples/public_company_research_assistant/benchmark.yaml --agent-name public_company_research_assistant
```
