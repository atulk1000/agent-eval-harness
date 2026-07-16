# Public Company Research Assistant Adapter

Status: Implemented in AgentEval 1.2.0

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

## Implemented Capture Path

No PCA source change is required. AgentEval's standalone capture worker imports PCA's public `answer_question` function inside PCA's own Python environment and stores the raw response:

```powershell
python -m agenteval.cli capture-pca --pca-repo ../public-company-research-assistant --pca-python ../public-company-research-assistant/.venv/Scripts/python.exe --benchmark examples/public_company_research_assistant/benchmark.json --out-responses runs/pca/raw_responses.jsonl
```

The offline adapter then converts raw response objects into AgentEval-compatible run objects. This split lets capture use PCA dependencies while validation and scoring remain standard-library-only.

Example adapted run object:

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

## AgentEval Commands

AgentEval adapts, validates, and scores the response file:

```powershell
python -m agenteval.cli adapt-pca --responses runs/pca/raw_responses.jsonl --benchmark examples/public_company_research_assistant/benchmark.json --out-trace runs/pca/traces.jsonl
python -m agenteval.cli validate --trace runs/pca/traces.jsonl
python -m agenteval.cli score --trace runs/pca/traces.jsonl --benchmark examples/public_company_research_assistant/benchmark.json --agent-name public_company_research_assistant --out runs/pca-scored
```

Summary-only PCA reports are rejected because they do not contain the SQL rows or retrieved chunks required for evidence-level scoring.

## Acceptance Criteria For Full Integration

- AgentEval captures PCA raw responses and adapts them to versioned JSONL traces.
- AgentEval scores at least one SQL-only, one RAG-only, and one hybrid PCA case.
- The imported PCA score report shows route mismatch, SQL evidence, retrieval evidence, and citation/faithfulness metadata.
- No sample trace claims to contain evidence that PCA did not actually export.
