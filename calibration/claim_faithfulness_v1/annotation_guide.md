# Annotation Guide

Review `cases.jsonl` or use the Streamlit Calibration tab with Blind review enabled. Do not open `proposals.jsonl` while assigning an independent label.

## Verdicts

- `supported`: every material part is directly established by the evidence.
- `partially_supported`: the core is supported but a material qualifier, number, cause, scope, or attribution is not.
- `unsupported`: relevant evidence exists but does not establish the claim.
- `contradicted`: evidence directly conflicts with the claim.
- `not_enough_evidence`: missing, failed, ambiguous, or inaccessible evidence prevents a reliable decision.

## Workflow

1. A primary reviewer labels all 100 cases with verdict, severity, evidence references, and rationale.
2. A second reviewer independently labels the 20 held-out cases.
3. Disagreements receive an adjudicator label.
4. Run `agenteval adjudicate` to create `gold.jsonl`.
5. Run `agenteval calibrate` only after gold creation.
