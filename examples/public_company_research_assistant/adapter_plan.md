# Public Company Research Assistant Adapter Plan

## Source Repo

`C:\Users\incre\OneDrive\Documents\Github\public-company-research-assistant`

Relevant source files:

- `evals/run_eval.py`
- `evals/benchmark_questions.yaml`
- `evals/latest_eval_report.json`
- `docs/evaluation.md`
- `docs/eval_results.md`

## Source Evaluation Fields

PCA currently reports case-level fields such as:

- `question`
- `expected_route`
- `actual_route`
- `sql_present`
- `sql_rows_nonempty`
- `retrieval_present`
- `retrieval_nonempty`
- `citations_present`
- `faithfulness_proxy_pass`
- `passed`
- `notes`

These are useful for aggregate quality checks, but they are not yet equivalent to AgentEval's trace schema.

## AgentEval Trace Mapping

Recommended mapping:

| PCA concept | AgentEval trace field |
| --- | --- |
| benchmark case id | `task_id` |
| question | benchmark `prompt` |
| actual route | route/planning event metadata |
| structured SQL | `tool=sql_query`, `input.query` |
| structured rows | `tool=sql_query`, `output.rows` |
| retrieved filing chunks | `tool=rag_search`, `output.documents` |
| final answer | `final_answer` |
| citations | final answer text or evidence refs |
| route mismatch note | score/failure metadata |

## Required PCA Exporter Change

Add an optional trace-export mode to PCA's `evals/run_eval.py`:

```powershell
python evals/run_eval.py --export-agenteval-trace out/pca_trace.jsonl
```

For each case, export one AgentEval-compatible run object:

```json
{
  "run_id": "pca_route_rag_amzn_strategy",
  "task_id": "route_rag_amzn_strategy",
  "agent_name": "public_company_research_assistant",
  "model": "pca-current",
  "final_answer": "...",
  "trace": [
    {
      "step": 1,
      "type": "tool_call",
      "tool": "sql_query",
      "input": {"query": "..."},
      "output": {"rows": []},
      "success": true,
      "error": null,
      "latency_ms": 0
    },
    {
      "step": 2,
      "type": "tool_call",
      "tool": "rag_search",
      "input": {"query": "..."},
      "output": {"documents": []},
      "success": true,
      "error": null,
      "latency_ms": 0
    }
  ]
}
```

## AgentEval Side Change

AgentEval already supports trace import:

```powershell
python -m agenteval.cli score --trace path/to/traces.jsonl --benchmark path/to/benchmark.yaml --agent-name external_trace
```

v1.2 can add a dedicated PCA adapter only after PCA exports enough trace detail to avoid fabricating evidence.

## Acceptance Criteria For Full Integration

- PCA exports AgentEval-compatible JSONL traces.
- AgentEval scores at least one SQL-only, one RAG-only, and one hybrid PCA case.
- The imported PCA score report shows route mismatch, SQL evidence, retrieval evidence, and citation/faithfulness metadata.
- No sample trace claims to contain evidence that PCA did not actually export.
