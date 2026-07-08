# AgentEval Harness

## PRD And Implementation Plan

Status: Draft for v1 implementation  
Project name: AgentEval Harness  
Repository name: agent-eval-harness  
Demo domain: B2B SaaS customer intelligence and renewal risk  
Primary stack: Python, SQLite, Streamlit, PyYAML, pytest, optional OpenAI-compatible judge API  
Current release scope: Local MVP with demo agent, benchmark suite, trace scoring, external trace import, and Streamlit dashboard

## 1. Product Summary

AgentEval Harness is a local evaluation framework for testing whether hybrid SQL + RAG agents choose the right tools, execute SQL correctly, retrieve grounded evidence, avoid unsupported claims, and synthesize structured and unstructured facts faithfully.

The MVP evaluates a fictional enterprise assistant that answers customer intelligence and renewal-risk questions using both a SQL database and an unstructured document corpus. The harness captures each observable agent run as a trace, scores the run with deterministic and judge-based evaluators, generates machine-readable artifacts, and exposes results in a Streamlit dashboard for technical and less-technical reviewers.

The product should feel like an agent quality control plane, not a generic chatbot demo.

## 2. Problem

Hybrid enterprise agents are hard to evaluate because final-answer quality is not enough. An answer can sound correct while the agent used the wrong tool, ignored retrieved evidence, invented unsupported claims, misreported SQL results, or mixed up which source supported which fact.

Common failure modes:

- The agent uses RAG for numeric business facts that should come from SQL.
- The agent uses SQL for policy or account-note questions that require documents.
- The SQL query executes but returns the wrong customers or aggregates.
- Retrieval finds irrelevant documents or misses required evidence.
- The final answer adds causal explanations not present in SQL results or retrieved documents.
- The agent combines the right facts with the wrong customer or source.
- The agent gives a confident answer after a tool error or missing evidence.
- Reviewers cannot easily inspect how the agent got its answer.

AgentEval solves this by evaluating the full observable run:

```text
benchmark task -> agent run -> tool trace -> evidence bundle -> final answer -> scores/report/dashboard
```

## 3. MVP Goals

The MVP must demonstrate an end-to-end agent evaluation workflow:

- Define trace-aware benchmark tasks for SQL-only, RAG-only, and hybrid SQL + RAG questions.
- Run a built-in demo hybrid agent against a benchmark suite.
- Capture every observable tool call and final answer in a structured trace.
- Score tool routing, SQL correctness, retrieval match, answer grounding, unsupported claims, cross-source synthesis, efficiency, and failure handling.
- Generate JSON/JSONL artifacts and a Markdown report for each run.
- Provide a Streamlit dashboard for non-technical validation of scores, traces, evidence, and unsupported claims.
- Compare at least two demo agent configurations or runs.
- Support external agents through trace import.
- Keep hidden chain-of-thought out of the trace and evaluation contract.

## 4. Non-Goals For MVP

The MVP will not include:

- Hosted SaaS deployment.
- Authentication, roles, or workspace management.
- Arbitrary MCP server evaluation.
- Browser automation.
- Multi-agent simulations.
- Human approval workflows.
- Fine-tuning.
- Large public benchmark marketplace.
- Production vector database operations.
- Real customer data.
- Full observability vendor integration.
- Evaluation of hidden chain-of-thought.

## 5. Primary Users

Primary personas:

- AI engineers building tool-using enterprise agents.
- LLM evaluation engineers designing benchmark and regression workflows.
- Forward-deployed engineers validating customer-specific AI behavior.
- AI product engineers comparing model and planner configurations.

Secondary personas:

- Hiring managers or recruiters reviewing the project demo.
- Less-technical stakeholders who need to understand whether an agent can be trusted.
- Engineering leads reviewing quality gates before deploying an agent workflow.

## 6. Product Principles

- Evaluate observable behavior, not hidden reasoning.
- Treat final answers as only one part of agent quality.
- Prefer deterministic scoring where facts are machine-verifiable.
- Use LLM judges only for semantic judgments that need language understanding.
- Judge final answers against the evidence the agent actually saw in the trace.
- Keep SQL facts, document facts, and hybrid synthesis separately inspectable.
- Make unsupported claims visible, specific, and evidence-linked.
- Keep the system local-first and easy to run.
- Make reports useful to both technical and less-technical reviewers.
- Design focused SQL + RAG support first, with extensible internals.

## 7. Demo Domain

The MVP uses a fictional B2B SaaS company evaluating customer health, revenue trends, support burden, product usage, contract terms, and renewal risk.

SQL data should include:

- `customers`
- `invoices`
- `subscriptions`
- `product_usage`
- `support_tickets`
- `renewals`

Document corpus should include:

- Account notes.
- Contract snippets.
- Renewal policy excerpts.
- Support summaries.
- Customer success notes.

Example questions:

```text
SQL-only:
Which enterprise customers had Q2 revenue below $50,000?

RAG-only:
What does the enterprise renewal policy require before approving a discount?

Hybrid:
Which enterprise customers had declining Q2 revenue, and do their account notes suggest renewal risk?
```

## 8. Agent Under Test

The built-in demo agent is a hybrid enterprise assistant with access to four tools:

- `schema_lookup`
- `sql_query`
- `rag_search`
- `document_lookup`

The demo agent should be simple but realistic:

- Read a benchmark prompt.
- Choose which tools to call.
- Use SQL for structured facts.
- Use RAG for unstructured context.
- Produce a final answer.
- Emit a trace through the harness.

The MVP should include two demo configurations:

- `baseline_agent`: intentionally weaker, with realistic mistakes such as missing RAG context or overclaiming.
- `improved_agent`: better routing, clearer uncertainty, and fewer unsupported claims.

This makes run comparison meaningful in the dashboard.

## 9. Tool Responsibilities

### `schema_lookup`

Use for discovering available tables, columns, and field meanings.

Expected usage:

- Before SQL tasks where schema context is needed.
- During recovery after a missing-table or missing-column SQL error.

### `sql_query`

Use for structured numeric and entity facts.

Examples:

- Revenue by quarter.
- Product usage trends.
- Ticket counts.
- Renewal dates.
- Customer segment filters.

The SQL tool must be read-only in MVP. It should allow only `SELECT` and `WITH ... SELECT` statements.

### `rag_search`

Use for finding unstructured evidence.

Examples:

- Account notes.
- Contract terms.
- Renewal policy excerpts.
- Support summaries.
- Customer success context.

### `document_lookup`

Use for opening a specific retrieved document or chunk when exact wording, policy language, or stronger evidence is needed.

This tool is optional for many MVP tasks if `rag_search` returns sufficient snippets.

## 10. Benchmark Task Format

Benchmarks should be YAML specs. Each task should encode the prompt, expected route, expected facts, relevant evidence, and scoring weights.

Example:

```yaml
id: hybrid_renewal_risk_001
task_type: hybrid_sql_rag
prompt: >
  Which enterprise customers had declining Q2 revenue,
  and do their account notes suggest renewal risk?

allowed_tools:
  - schema_lookup
  - sql_query
  - rag_search
  - document_lookup

expected_route:
  required_tools:
    - schema_lookup
    - sql_query
    - rag_search
  optional_tools:
    - document_lookup
  forbidden_tools: []

expected_sql:
  required_tables:
    - customers
    - invoices
  result_facts:
    - customer: Acme Health
      fact: Q2 revenue declined from Q1
    - customer: Northstar Bank
      fact: Q2 revenue declined from Q1

expected_documents:
  relevant_doc_ids:
    - account_note_acme_2026_06
    - account_note_northstar_2026_06

expected_answer_facts:
  - Acme Health had declining Q2 revenue
  - Northstar Bank had declining Q2 revenue
  - Acme Health has renewal risk due to unresolved onboarding issues
  - Northstar Bank has renewal risk due to executive sponsor concerns

unsupported_claim_traps:
  - Do not claim churn has already occurred.
  - Do not claim discounts were approved unless found in retrieved documents.

rubric:
  tool_routing: 2
  sql_correctness: 2
  retrieval_grounding: 2
  faithfulness: 2
  synthesis: 1
  efficiency: 1
```

## 11. Benchmark Suite

The MVP benchmark suite should include 15 tasks:

- 5 SQL-only tasks.
- 5 RAG-only tasks.
- 5 hybrid SQL + RAG tasks.

Task types:

```text
sql_only
rag_only
hybrid_sql_rag
```

The suite should contain at least one example of each major failure mode:

- Missing required tool.
- Wrong tool for task.
- SQL false positive row.
- SQL missing expected row.
- Missing relevant document.
- Unsupported document claim.
- Cross-entity evidence mismatch.
- Overstated synthesis.
- Confident answer after insufficient evidence.

## 12. Correctness Definition

Correctness means evidence-grounded task completion:

- The answer addresses the user prompt.
- SQL-backed facts match database results.
- Document-backed claims are supported by retrieved evidence.
- Hybrid conclusions preserve the relationship between entities, sources, and uncertainty.
- The final answer avoids unsupported claims.

For hybrid tasks, a correct answer should clearly separate:

- Structured facts from SQL.
- Qualitative context from documents.
- Synthesis or risk interpretation.
- Caveats when evidence is incomplete.

## 13. Scoring Architecture

The scoring engine should combine deterministic scorers and judge-based scorers.

### Deterministic Scorers

Implement first:

- `tool_route_scorer`
- `sql_execution_scorer`
- `sql_result_scorer`
- `retrieval_match_scorer`
- `expected_fact_presence_scorer`
- `efficiency_scorer`
- `trace_error_scorer`

Use deterministic scoring for:

- Did the required tool run?
- Did a forbidden tool run?
- Did SQL execute successfully?
- Was SQL read-only?
- Did SQL return expected rows and values?
- Did retrieval include expected documents?
- Did the answer include expected entities or key facts?
- Did the agent exceed the tool-call budget?
- Did the agent continue confidently after a failed tool call?

### Judge-Based Scorers

Implement through a judge interface with mock fallback and optional real LLM support:

- `faithfulness_judge`
- `unsupported_claim_judge`
- `answer_completeness_judge`
- `cross_source_synthesis_judge`
- `source_attribution_judge`
- `insufficient_evidence_judge`

Use judge-based scoring for:

- Is each factual claim supported by SQL results or retrieved documents?
- Did the answer address every part of the prompt?
- Did the answer combine SQL and RAG evidence correctly?
- Did the answer misattribute a document fact to SQL or a SQL fact to documents?
- Did the answer state uncertainty when evidence was missing?

## 14. Unsupported Claim Detection

Unsupported claim detection is a flagship feature.

Process:

```text
final answer -> claim extraction -> evidence verification -> verdict and severity
```

Evidence bundle:

- SQL query outputs.
- Retrieved document chunks.
- Opened documents.
- Tool errors.
- Schema info.

Per-claim verdict labels:

- `supported`
- `partially_supported`
- `unsupported`
- `contradicted`
- `not_enough_evidence`

Severity labels:

- `low`: minor wording or weak attribution issue.
- `medium`: unsupported explanation or incomplete grounding.
- `high`: invented number, business event, customer status, or claim contradicted by evidence.

Example output:

```json
{
  "claim": "Northstar requested a 20% discount",
  "verdict": "unsupported",
  "severity": "high",
  "reason": "No SQL result or retrieved document mentions a discount request.",
  "evidence_refs": []
}
```

## 15. Tool Selection Scoring

Tool selection is scored by comparing the benchmark's expected route with the actual trace.

Failure labels:

- `missing_required_tool`
- `wrong_tool_for_task`
- `unnecessary_tool`
- `forbidden_tool_used`
- `bad_tool_order`
- `premature_final_answer`
- `tool_loop`
- `failed_tool_recovery`

Suggested weighting:

- Required tools used: 50%.
- Wrong or forbidden tools avoided: 20%.
- Route/order quality: 15%.
- No premature final answer: 10%.
- Reasonable call count: 5%.

Tool order should be soft-scored unless the benchmark explicitly marks order as strict.

## 16. SQL Correctness Scoring

SQL scoring should primarily evaluate executed results, not exact SQL text.

Checks:

- Query executed successfully.
- Query was read-only.
- Query referenced allowed and expected tables.
- Result rows matched expected facts.
- Result did not include false-positive rows.
- Numeric values matched within configured tolerance.
- Final answer accurately reflected SQL result values.

Example output:

```json
{
  "score": 0.82,
  "executed": true,
  "read_only": true,
  "required_tables_used": ["customers", "invoices"],
  "missing_expected_rows": [],
  "unexpected_rows": ["BrightCart"],
  "numeric_mismatches": [],
  "failure_labels": ["sql_false_positive_row"]
}
```

## 17. RAG Quality Scoring

RAG quality should be split into retrieval quality and answer grounding.

Retrieval checks:

- Expected documents retrieved.
- Required document chunks present in top results.
- Irrelevant documents minimized.
- Relevant evidence rank is reasonable.

Grounding checks:

- Document-based claims are supported by retrieved or opened documents.
- Missing evidence is acknowledged.
- The answer does not invent document details.

Example output:

```json
{
  "retrieval_score": 0.67,
  "grounding_score": 0.8,
  "expected_docs_found": ["account_note_acme_2026_06"],
  "missing_docs": ["account_note_northstar_2026_06"],
  "irrelevant_docs": ["random_support_note_brightcart"],
  "unsupported_doc_claims": [
    "Northstar requested a 20% discount"
  ],
  "failure_labels": [
    "missing_relevant_document",
    "unsupported_doc_claim"
  ]
}
```

## 18. Hybrid Reasoning Scoring

Hybrid reasoning is scored by whether the agent uses the right source for each fact type and preserves the mapping between entities, sources, evidence, and uncertainty.

SQL should support:

- What happened.
- How much.
- How many.
- Which customers.
- When.

RAG should support:

- Why something might be happening.
- What notes, contracts, or policies say.
- Qualitative risk signals.
- Caveats and context.

Failure labels:

- `missing_structured_evidence`
- `missing_unstructured_evidence`
- `overstated_synthesis`
- `cross_entity_evidence_mismatch`
- `wrong_source_attribution`
- `unsupported_causal_claim`
- `insufficient_evidence_overclaim`

Example output:

```json
{
  "score": 0.72,
  "structured_facts_used": true,
  "unstructured_evidence_used": true,
  "entity_alignment": 0.5,
  "source_attribution": 0.8,
  "unsupported_synthesis_claims": [
    "Acme will churn next quarter"
  ],
  "failure_labels": [
    "overstated_synthesis",
    "cross_entity_evidence_mismatch"
  ]
}
```

## 19. Trace Schema

The trace schema should be JSON/JSONL, run-centered, and focused on observable behavior.

Run-level fields:

```json
{
  "run_id": "run_2026_07_001",
  "task_id": "hybrid_renewal_risk_001",
  "agent_name": "improved_agent",
  "model": "demo-planner-v2",
  "started_at": "2026-07-07T10:00:00Z",
  "completed_at": "2026-07-07T10:00:03Z",
  "final_answer": "...",
  "trace": []
}
```

Tool event fields:

```json
{
  "step": 2,
  "type": "tool_call",
  "tool": "sql_query",
  "input": {
    "query": "SELECT customer_id, SUM(revenue) FROM invoices ..."
  },
  "output": {
    "rows": [
      {
        "customer": "Acme Health",
        "q1_revenue": 120000,
        "q2_revenue": 90000
      }
    ]
  },
  "success": true,
  "error": null,
  "latency_ms": 312
}
```

No chain-of-thought is required or stored.

## 20. External Agent Support

The MVP should support external agents through trace import first.

Example:

```bash
agenteval score --trace runs/external_agent_trace.jsonl --benchmark benchmarks/customer_risk.yaml
```

Any external agent can be evaluated if it emits the expected trace schema.

Future adapter:

```python
class AgentUnderTest:
    def run(self, task, tools, trace) -> AgentRun:
        ...
```

## 21. CLI Requirements

The CLI should support:

```bash
agenteval run
agenteval score
agenteval report
agenteval compare
```

Example MVP commands:

```bash
agenteval run benchmarks/customer_risk.yaml --agent baseline_agent
agenteval run benchmarks/customer_risk.yaml --agent improved_agent
agenteval score --trace runs/external_agent_trace.jsonl --benchmark benchmarks/customer_risk.yaml
agenteval compare runs/baseline runs/improved
```

Each run should produce a timestamped output directory under `runs/`.

## 22. Run Artifacts

Each run should output:

- `traces.jsonl`
- `scores.json`
- `summary.json`
- `unsupported_claims.json`
- `report.md`

Optional later:

- `report.html`
- `comparison.json`
- `costs.json`
- `token_usage.json`

## 23. Streamlit Dashboard

The Streamlit dashboard should be designed for non-technical validation.

Pages:

- Overview.
- Task Results.
- Task Detail and Trace Viewer.
- Evidence Panel.
- Unsupported Claims.
- Compare Runs.

The dashboard should answer in under 30 seconds:

- Did the agent pass?
- Where did it fail?
- Which tools did it call?
- What evidence did it use?
- Which claims were unsupported?
- Which model or agent configuration performed better?

### Overview Page

Show:

- Overall score.
- Tasks passed and failed.
- Average tool-routing score.
- Average SQL correctness score.
- Average RAG grounding score.
- Unsupported claims count.
- High-severity failure count.

### Task Results Page

Table columns:

- `task_id`
- `task_type`
- `score`
- `expected_route`
- `actual_route`
- `status`
- `failure_labels`
- `unsupported_claim_count`

### Task Detail Page

Show:

- Prompt.
- Expected behavior.
- Final answer.
- Score breakdown.
- Failure labels.
- Trace timeline.

### Evidence Panel

Show:

- SQL result rows.
- Retrieved document snippets.
- Opened documents.
- Evidence references used by unsupported-claim analysis.

### Unsupported Claims Page

Show claim cards with:

- Claim text.
- Verdict.
- Severity.
- Reason.
- Evidence references.
- Related failure label.

### Compare Runs Page

Compare:

- Overall score delta.
- Score by dimension.
- Unsupported claim delta.
- Tool-call count.
- Latency.
- Failure labels by run.

## 24. Proposed Project Structure

```text
agent-eval-harness/
  README.md
  pyproject.toml
  agenteval/
    __init__.py
    cli.py
    runner.py
    benchmark.py
    trace.py
    tools.py
    data_loader.py
    scorers/
      __init__.py
      tool_routing.py
      sql_correctness.py
      retrieval.py
      facts.py
      efficiency.py
      judges.py
    reports/
      __init__.py
      markdown.py
      compare.py
    dashboard/
      app.py
      pages/
  agents/
    baseline_agent.py
    improved_agent.py
    adapters.py
  benchmarks/
    customer_risk.yaml
  data/
    seed_demo_db.py
    docs/
    sqlite/
  runs/
    .gitkeep
  tests/
    test_tool_routing.py
    test_sql_correctness.py
    test_retrieval_scoring.py
    test_trace_schema.py
  docs/
    prd_agent_eval_harness.md
```

## 25. Implementation Plan

### Phase 1: Project Skeleton

Build:

- Package structure.
- `pyproject.toml`.
- CLI entrypoint.
- Benchmark loader.
- Trace dataclasses or Pydantic models.
- Basic README.

Deliverable:

The project imports cleanly and the CLI can load benchmark YAML.

### Phase 2: Demo Data And Tools

Build:

- SQLite seed script.
- Fictional customer dataset.
- Document corpus.
- `schema_lookup`.
- read-only `sql_query`.
- simple lexical `rag_search`.
- `document_lookup`.
- trace wrappers for all tools.

Deliverable:

Tools run locally and produce trace events.

### Phase 3: Benchmark Suite

Build:

- 5 SQL-only tasks.
- 5 RAG-only tasks.
- 5 hybrid tasks.
- Expected routes, facts, docs, and rubrics.

Deliverable:

Benchmark suite validates against schema and can be run by the harness.

### Phase 4: Demo Agents

Build:

- `baseline_agent`.
- `improved_agent`.
- Agent registry.
- Agent run interface.

Deliverable:

Both demo agents can run all 15 tasks and emit traces.

### Phase 5: Deterministic Scoring

Build:

- Tool route scorer.
- SQL execution/result scorer.
- Retrieval match scorer.
- Expected fact scorer.
- Efficiency scorer.
- Trace error scorer.

Deliverable:

Each run produces `scores.json` and `summary.json`.

### Phase 6: Judge Interface And Unsupported Claims

Build:

- Judge interface.
- Mock judge fallback.
- Optional OpenAI-compatible judge client.
- Claim extraction and verification output schema.
- Unsupported claim severity labels.

Deliverable:

Runs include `unsupported_claims.json`, with mock or real judge support.

### Phase 7: Reports

Build:

- Markdown report generator.
- Comparison summary.
- Run artifact writer.

Deliverable:

Each run has a readable `report.md`; two runs can be compared.

### Phase 8: Streamlit Dashboard

Build:

- Overview page.
- Task results table.
- Task detail trace viewer.
- Evidence panel.
- Unsupported claims panel.
- Compare runs page.

Deliverable:

Dashboard can load `runs/` artifacts and explain agent quality to a non-technical reviewer.

### Phase 9: External Trace Import

Build:

- `agenteval score --trace ...`.
- Trace schema validation.
- Imported trace scoring path.

Deliverable:

An external trace can be evaluated without using the built-in demo agent.

## 26. Acceptance Criteria

MVP is complete when:

- `agenteval run benchmarks/customer_risk.yaml --agent baseline_agent` completes.
- `agenteval run benchmarks/customer_risk.yaml --agent improved_agent` completes.
- Each run writes `traces.jsonl`, `scores.json`, `summary.json`, `unsupported_claims.json`, and `report.md`.
- Deterministic scorers catch missing tools, SQL errors, wrong SQL results, missed documents, and inefficient traces.
- Unsupported claim output includes claim, verdict, severity, reason, and evidence references.
- Streamlit dashboard loads generated run artifacts.
- Dashboard shows run overview, task table, trace timeline, evidence, unsupported claims, and comparison view.
- Improved agent scores better than baseline on hybrid synthesis and unsupported claims.
- External trace import can score a valid trace file.
- Tests cover benchmark loading, trace schema, SQL scorer, retrieval scorer, and tool routing scorer.

## 27. Success Metrics

Portfolio/demo success:

- A reviewer can understand the product in under 2 minutes.
- A reviewer can inspect one failed task and see exactly why it failed.
- The dashboard clearly shows at least one unsupported claim and the missing evidence.
- The comparison view shows measurable improvement from baseline to improved agent.

Technical success:

- Benchmark tasks are version-controlled and readable.
- Scoring outputs are machine-readable.
- SQL checks are result-based, not exact-query based.
- RAG checks separate retrieval match from answer grounding.
- External traces can be scored without modifying the harness.

## 28. Risks And Mitigations

Risk: The project looks like a generic eval dashboard.  
Mitigation: Keep the positioning focused on trace-based hybrid SQL + RAG agent behavior.

Risk: The LLM judge makes results feel subjective.  
Mitigation: Use deterministic scorers first and make judge outputs structured and evidence-linked.

Risk: The demo agent becomes the main project.  
Mitigation: Keep the demo agent simple and emphasize trace schema, scoring, artifacts, and dashboard.

Risk: Streamlit work distracts from core scoring.  
Mitigation: Build the dashboard only on generated artifacts after the CLI scoring path works.

Risk: RAG retrieval quality is weak without embeddings.  
Mitigation: Start with lexical retrieval over curated demo docs; embeddings can be a later enhancement.

Risk: External agent support becomes too broad.  
Mitigation: Support trace import first; Python adapter can follow.

## 29. Interview Positioning

Concise project pitch:

> AgentEval Harness is a trace-based evaluation framework for hybrid SQL + RAG agents. It benchmarks whether an agent chooses the right tools, executes SQL correctly, retrieves grounded evidence, avoids unsupported claims, and synthesizes structured and unstructured facts faithfully. The system ships with a demo B2B SaaS customer-risk agent, external trace import, deterministic and judge-based scoring, and a Streamlit dashboard for reviewing failures and comparing agent configurations.

Resume bullet:

> Built AgentEval Harness, a trace-based evaluation framework for hybrid SQL + RAG agents that captures tool traces, scores SQL correctness and retrieval grounding, detects unsupported claims, compares agent configurations, and visualizes eval failures in a Streamlit dashboard.

## 30. Initial Build Order

Recommended first commits:

1. Add project skeleton, PRD, and README.
2. Add demo SQLite seed data and document corpus.
3. Add benchmark schema and 15 task YAML file.
4. Add traced tool wrappers.
5. Add baseline and improved demo agents.
6. Add deterministic scorers and artifact writer.
7. Add judge interface and unsupported claim output.
8. Add Markdown report.
9. Add Streamlit dashboard.
10. Add external trace import and tests.
