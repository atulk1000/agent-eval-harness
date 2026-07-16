# AgentEval Harness v1.1 Plan

Historical plan: completed in v1.1. The planned PCA bridge is implemented in v1.2; see [prd_v1_2_independent_proof.md](prd_v1_2_independent_proof.md).

## Goal

Move AgentEval Harness from a credible MVP to a reviewer-ready portfolio project.

v1.1 should make the project easier to trust in under two minutes by adding CI, clearer proof artifacts, a guided reviewer path, and a concrete bridge to external traces from the Public Company Research Assistant project.

## Review Input

The external review rated the project:

- Current repo maturity: 7.5/10.
- After CI, proof artifacts, and README polish: 8.5/10.
- With Public Company Research Assistant trace integration: 9/10.

The review agreed that the core concept is strong:

- Trace-based evaluation.
- Hybrid SQL + RAG agent focus.
- Deterministic and judge-style scoring split.
- Unsupported-claim detection.
- Baseline vs improved agent comparison.
- Local CLI plus Streamlit dashboard.

The main issue is not product direction. The main issue is proof and maturity.

## v1.1 Scope

v1.1 should include:

1. GitHub Actions CI.
2. Line-ending normalization.
3. README reviewer path.
4. README sample run results.
5. README unsupported-claim example.
6. Checked-in sample proof artifacts, or a clearly documented way to regenerate them.
7. A scoped Public Company Research Assistant integration plan or adapter stub.

## Non-Goals

v1.1 will not include:

- A hosted dashboard.
- Real LLM judge integration.
- Production vector database support.
- Full MCP trace capture.
- A complete rewrite of Public Company Research Assistant.
- A large benchmark marketplace.
- Authentication or multi-user run management.

## Workstream 1: CI

Add `.github/workflows/ci.yml`.

Minimum workflow:

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: python -m pip install --upgrade pip
      - run: pip install -e ".[dev]"
      - run: python -m compileall agenteval agents tests
      - run: python -m unittest discover -s tests
```

Acceptance criteria:

- CI appears on GitHub.
- CI passes on `main`.
- README includes a CI badge after the first successful run.

## Workstream 2: Line Endings And Git Hygiene

Add `.gitattributes`.

Recommended content:

```gitattributes
* text=auto
*.py text eol=lf
*.md text eol=lf
*.yml text eol=lf
*.yaml text eol=lf
*.toml text eol=lf
*.json text eol=lf
*.jsonl text eol=lf
```

Acceptance criteria:

- GitHub README renders cleanly.
- Source files have predictable line endings.
- Generated run artifacts, SQLite DB files, and generated document corpus remain ignored.

## Workstream 3: README Reviewer Path

Add a reviewer path near the top of `README.md`.

Draft:

```markdown
## Reviewer Path

To review this project quickly:

1. Start with `docs/prd_agent_eval_harness.md` for product scope.
2. Inspect `benchmarks/customer_risk.yaml` for trace-aware benchmark tasks.
3. Review `agenteval/trace.py` for the observable trace schema.
4. Review `agenteval/scorers/` for tool routing, SQL, retrieval, facts, efficiency, and judge scoring.
5. Run baseline vs improved agents using the Quick Start commands.
6. Open the comparison artifact or launch the Streamlit dashboard to inspect failures.
```

Acceptance criteria:

- A hiring manager can skim the repo in a clear order.
- A technical reviewer knows exactly where the core implementation lives.

## Workstream 4: README Proof Artifacts

Surface current sample results.

Use the latest validated local run:

| Agent | Overall | Passed | Failed | Unsupported Claims | High Severity |
| --- | ---: | ---: | ---: | ---: | ---: |
| `baseline_agent` | 0.859 | 10 | 5 | 4 | 4 |
| `improved_agent` | 0.970 | 15 | 0 | 0 | 0 |

Add a short interpretation:

- Baseline demonstrates realistic failures: unsupported discount approval, churn overclaim, missing RAG context, weaker source attribution.
- Improved agent demonstrates better routing, grounding, synthesis, and caveat behavior.

Acceptance criteria:

- README shows why the benchmark is useful without requiring the reviewer to run it.
- Results match the generated local artifacts.

## Workstream 5: Unsupported-Claim Example

Add one concrete unsupported-claim example to the README.

Use an actual baseline artifact:

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

Acceptance criteria:

- The README makes unsupported-claim detection visually obvious.
- The example is copied from generated output, not invented.

## Workstream 6: Proof Artifact Strategy

There are two viable options.

### Option A: Keep generated runs ignored

Pros:

- Repo stays clean.
- Avoids stale generated artifacts.
- Current `.gitignore` already supports this.

Need:

- README must tell reviewers how to regenerate artifacts.

### Option B: Check in curated sample artifacts

Suggested path:

```text
examples/sample_runs/
  baseline_summary.json
  improved_summary.json
  comparison.json
  unsupported_claims.json
```

Pros:

- GitHub reviewers can inspect proof without running code.
- Stronger portfolio signal.

Cons:

- Need to keep examples synced when scoring changes.

Decision for v1.1:

Use Option B with a small curated subset, not full run traces.

Acceptance criteria:

- `examples/sample_runs/` includes compact artifacts.
- README links to these artifacts.
- Full generated `runs/` remains ignored.

## Workstream 7: Public Company Research Assistant Bridge

The review recommends connecting AgentEval to Public Company Research Assistant traces.

Current reality:

- Public Company Research Assistant has an eval layer under `evals/`.
- It has benchmark questions and `latest_eval_report.json`.
- It does not yet emit AgentEval trace schema directly.

v1.1 should avoid faking a trace. Instead, add a concrete bridge.

Recommended v1.1 deliverable:

```text
examples/public_company_research_assistant/
  README.md
  adapter_plan.md
  sample_eval_report_excerpt.json
```

README should say:

> Public Company Research Assistant already evaluates SQL/RAG/hybrid financial research behavior. AgentEval v1.1 documents the adapter boundary for converting that repo's eval output into AgentEval's trace schema. Full live trace export is planned for v1.2.

Optional if time allows:

- Add `agenteval/adapters/public_company.py`.
- Convert one `latest_eval_report.json` case into a synthetic AgentEval-compatible imported trace only if the required fields are actually present.

Acceptance criteria:

- The repo clearly explains how AgentEval can evaluate external SQL + RAG systems.
- It references Public Company Research Assistant honestly as an integration target.
- No fake trace evidence is presented as real.

## Recommended Execution Order

1. Add CI.
2. Add `.gitattributes`.
3. Add curated sample artifacts.
4. Update README with reviewer path, sample results, unsupported-claim example, and artifact links.
5. Add Public Company Research Assistant bridge docs.
6. Run tests and local demo commands.
7. Commit and push v1.1.

## Validation Commands

Run before commit:

```powershell
python -m compileall agenteval agents tests
python -m unittest discover -s tests
python -m agenteval.cli run benchmarks/customer_risk.yaml --agent baseline_agent --out runs/baseline
python -m agenteval.cli run benchmarks/customer_risk.yaml --agent improved_agent --out runs/improved
python -m agenteval.cli compare runs/baseline runs/improved --out runs/comparison
python -m agenteval.cli score --trace runs/improved/traces.jsonl --benchmark benchmarks/customer_risk.yaml --agent-name imported_improved --out runs/imported_improved
```

Expected local result:

- Baseline: 10/15 passed, 4 unsupported claims, overall around 0.859.
- Improved: 15/15 passed, 0 unsupported claims, overall around 0.970.
- Imported improved trace: matches improved score.

## v1.1 Definition Of Done

v1.1 is done when:

- GitHub Actions CI exists and passes.
- README has reviewer path and proof artifacts.
- README shows baseline vs improved result table.
- README shows at least one unsupported-claim example.
- `.gitattributes` is present.
- Curated sample artifacts are checked in under `examples/sample_runs/`.
- Public Company Research Assistant bridge is documented.
- Local tests pass.
- Changes are committed and pushed to GitHub.
