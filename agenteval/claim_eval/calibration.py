"""Reproducible calibration-dataset construction."""

from __future__ import annotations

import copy
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from agenteval.claim_eval.evidence import EvidenceSelector
from agenteval.claim_eval.judging import CompositeClaimJudge
from agenteval.claim_eval.models import SCHEMA_VERSION, stable_id, validate_claim, validate_evidence
from agenteval.claim_eval.providers import RuleOnlyJudgeProvider
from agenteval.runner import run_suite, score_trace_file
from agenteval.trace import read_json, read_jsonl, write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[2]
SOURCE_TARGETS = {
    "customer_risk": 30,
    "public_company": 20,
    "adversarial": 40,
    "tool_failure": 10,
}
MUTATION_TYPES = (
    "altered_number",
    "entity_swap",
    "unsupported_status",
    "negation",
    "causal_overreach",
    "policy_approval",
    "partial_scope",
    "correct_paraphrase",
)


def build_calibration_dataset(
    output_dir: str | Path,
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    repo_root = Path(root) if root else ROOT
    output = Path(output_dir)
    _protect_human_work(output)
    output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="agenteval-calibration-") as temporary:
        temp = Path(temporary)
        improved = run_suite(
            repo_root / "benchmarks" / "customer_risk.yaml",
            "improved_agent",
            output_dir=temp / "improved",
        )
        baseline = run_suite(
            repo_root / "benchmarks" / "customer_risk.yaml",
            "baseline_agent",
            output_dir=temp / "baseline",
        )
        pca = score_trace_file(
            repo_root / "examples" / "public_company_research_assistant" / "benchmark.json",
            repo_root / "examples" / "public_company_research_assistant" / "proof" / "traces.jsonl",
            output_dir=temp / "pca",
            agent_name="public_company_research_assistant",
        )
        customer_seed = _cases_from_runs([improved, baseline], "customer_risk")
        pca_seed = _cases_from_runs([pca], "public_company")

    customer = _expand_cases(customer_seed, SOURCE_TARGETS["customer_risk"], "customer_risk")
    public_company = _expand_cases(pca_seed, SOURCE_TARGETS["public_company"], "public_company")
    base = customer + public_company
    adversarial = [_mutate_case(base[index % len(base)], index) for index in range(40)]
    failures = [_failure_case(base[index % len(base)], index) for index in range(10)]
    pairs = customer + public_company + adversarial + failures
    _assign_splits(pairs)

    cases = [pair["case"] for pair in pairs]
    proposals = [pair["proposal"] for pair in pairs]
    write_jsonl(output / "cases.jsonl", cases)
    write_jsonl(output / "proposals.jsonl", proposals)
    annotations_dir = output / "annotations"
    annotations_dir.mkdir(exist_ok=True)
    for name in ("primary.jsonl", "independent.jsonl", "adjudicator.jsonl"):
        path = annotations_dir / name
        if not path.exists():
            write_jsonl(path, [])

    source_counts = Counter(case["source_group"] for case in cases)
    split_counts = Counter(case["split"] for case in cases)
    mutation_counts = Counter(
        case.get("mutation_type") for case in cases if case.get("mutation_type")
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": "claim_faithfulness_v1",
        "status": "proposed_labels_pending_human_review",
        "case_count": len(cases),
        "source_counts": dict(sorted(source_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "mutation_counts": dict(sorted(mutation_counts.items())),
        "source_trace_counts": {
            "customer_risk": len({pair["case"].get("source_run_id") for pair in customer}),
            "public_company": len({pair["case"].get("source_run_id") for pair in public_company}),
        },
        "source_pool_trace_counts": {"customer_risk": 30, "public_company": 3},
        "limitations": [
            "Machine proposals are not gold labels.",
            "The bundled PCA proof contains three source runs; twenty PCA cases use deterministic evidence-window variants from those runs.",
            "Primary and independent human review remain required before release gates can be claimed.",
        ],
    }
    write_json(output / "manifest.json", manifest)
    (output / "README.md").write_text(
        "# Claim Faithfulness Calibration Dataset\n\n"
        "`cases.jsonl` contains reviewer inputs. `proposals.jsonl` contains machine labels and must remain hidden during blind review.\n\n"
        "The dataset is not gold until primary review, independent held-out review, and adjudication are complete. See `annotation_guide.md`.\n",
        encoding="utf-8",
    )
    (output / "annotation_guide.md").write_text(
        "# Annotation Guide\n\n"
        "Review `cases.jsonl` or use the Streamlit Calibration tab with Blind review enabled. Do not open `proposals.jsonl` while assigning an independent label.\n\n"
        "## Verdicts\n\n"
        "- `supported`: every material part is directly established by the evidence.\n"
        "- `partially_supported`: the core is supported but a material qualifier, number, cause, scope, or attribution is not.\n"
        "- `unsupported`: relevant evidence exists but does not establish the claim.\n"
        "- `contradicted`: evidence directly conflicts with the claim.\n"
        "- `not_enough_evidence`: missing, failed, ambiguous, or inaccessible evidence prevents a reliable decision.\n\n"
        "## Workflow\n\n"
        "1. A primary reviewer labels all 100 cases with verdict, severity, evidence references, and rationale.\n"
        "2. A second reviewer independently labels the 20 held-out cases.\n"
        "3. Disagreements receive an adjudicator label.\n"
        "4. Run `agenteval adjudicate` to create `gold.jsonl`.\n"
        "5. Run `agenteval calibrate` only after gold creation.\n",
        encoding="utf-8",
    )
    return manifest


def _cases_from_runs(run_dirs: list[Path], source_group: str) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        scores = read_json(run_dir / "scores.json")
        traces = {row["task_id"]: row for row in read_jsonl(run_dir / "traces.jsonl")}
        for score in scores:
            evaluation = score["claim_evaluation"]
            evidence_by_id = {item["evidence_id"]: item for item in evaluation["evidence"]}
            claims = {item["claim_id"]: item for item in evaluation["claims"]}
            for verdict in evaluation["verdicts"]:
                claim = claims[verdict["claim_id"]]
                selected = [
                    copy.deepcopy(evidence_by_id[ref])
                    for ref in verdict.get("evidence_considered", [])
                    if ref in evidence_by_id
                ]
                if not selected:
                    selected = [copy.deepcopy(item) for item in evaluation["evidence"][:8]]
                pairs.append(
                    _base_pair(
                        claim,
                        selected,
                        verdict,
                        source_group=source_group,
                        source_name=run_dir.name,
                        task_type=score["task_type"],
                        final_answer=traces[score["task_id"]]["final_answer"],
                        variant=len(pairs),
                    )
                )
    return pairs


def _base_pair(
    claim: dict[str, Any],
    evidence: list[dict[str, Any]],
    verdict: dict[str, Any],
    *,
    source_group: str,
    source_name: str,
    task_type: str,
    final_answer: str,
    variant: int,
) -> dict[str, Any]:
    original_claim_id = claim["claim_id"]
    stable_run_id = stable_id("cal_run", source_group, source_name, claim["task_id"])
    new_claim_id = stable_id("cal_claim", source_group, source_name, original_claim_id, variant)
    case_id = stable_id("case", new_claim_id)
    copied_claim = copy.deepcopy(claim)
    copied_claim["claim_id"] = new_claim_id
    copied_claim["run_id"] = stable_run_id
    copied_evidence = []
    reference_map = {}
    for index, item in enumerate(evidence):
        copied_item = copy.deepcopy(item)
        original_evidence_id = copied_item["evidence_id"]
        new_evidence_id = stable_id(
            "cal_evidence",
            source_group,
            source_name,
            copied_item["task_id"],
            copied_item["tool_step"],
            copied_item["source_type"],
            index,
            copied_item["content"],
        )
        reference_map[original_evidence_id] = new_evidence_id
        copied_item["evidence_id"] = new_evidence_id
        copied_item["run_id"] = stable_run_id
        copied_item["provenance"]["trace_run_id"] = stable_run_id
        copied_evidence.append(copied_item)
    proposal = copy.deepcopy(verdict)
    proposal["claim_id"] = new_claim_id
    proposal["run_id"] = stable_run_id
    proposal["evidence_refs"] = [
        reference_map[ref] for ref in proposal.get("evidence_refs", []) if ref in reference_map
    ]
    proposal["evidence_considered"] = [
        reference_map[ref]
        for ref in proposal.get("evidence_considered", [])
        if ref in reference_map
    ]
    return {
        "case": {
            "schema_version": SCHEMA_VERSION,
            "case_id": case_id,
            "claim_id": new_claim_id,
            "source_claim_id": original_claim_id,
            "source_group": source_group,
            "source_run_id": stable_run_id,
            "source_trace_name": source_name,
            "task_id": claim["task_id"],
            "task_type": task_type,
            "final_answer": final_answer,
            "claim": copied_claim,
            "evidence": copied_evidence,
            "review_status": "pending",
        },
        "proposal": proposal,
    }


def _expand_cases(
    seed: list[dict[str, Any]], target: int, source_group: str
) -> list[dict[str, Any]]:
    if not seed:
        raise ValueError(f"no {source_group} calibration seeds were generated")
    expanded = []
    for index in range(target):
        source = copy.deepcopy(seed[index % len(seed)])
        if index >= len(seed):
            source = _reidentify(source, source_group, index)
            source["case"]["evidence_window_variant"] = index // len(seed) + 1
        expanded.append(source)
    return expanded


def _reidentify(pair: dict[str, Any], source_group: str, variant: int) -> dict[str, Any]:
    claim = pair["case"]["claim"]
    claim_id = stable_id("cal_claim", source_group, claim["claim_id"], variant)
    pair["case"]["claim_id"] = claim_id
    pair["case"]["case_id"] = stable_id("case", claim_id)
    claim["claim_id"] = claim_id
    pair["proposal"]["claim_id"] = claim_id
    return pair


def _mutate_case(source: dict[str, Any], index: int) -> dict[str, Any]:
    pair = copy.deepcopy(source)
    mutation = MUTATION_TYPES[index % len(MUTATION_TYPES)]
    claim = pair["case"]["claim"]
    text = str(claim["text"])
    subject = claim.get("subject") or "The entity"
    if mutation == "altered_number":
        match = re.search(r"\d+(?:\.\d+)?", text)
        text = (
            text[: match.start()]
            + str(float(match.group()) + 17).rstrip("0").rstrip(".")
            + text[match.end() :]
            if match
            else f"{subject} has a reported value of 999999."
        )
        claim["claim_type"] = "numeric"
    elif mutation == "entity_swap":
        text = (
            text.replace(str(subject), "Unseen Entity", 1)
            if subject
            else f"Unseen Entity has {text}"
        )
        claim["subject"] = "Unseen Entity"
        claim["claim_type"] = "entity_fact"
    elif mutation == "unsupported_status":
        text = f"{subject} has already churned."
        claim["claim_type"] = "business_status"
    elif mutation == "negation":
        text = f"The evidence does not contain {subject}."
        claim["claim_type"] = "entity_fact"
    elif mutation == "causal_overreach":
        text = "Pricing caused the reported change."
        claim["subject"] = "Pricing"
        claim["claim_type"] = "causal"
    elif mutation == "policy_approval":
        text = "The requested discount was automatically approved."
        claim["subject"] = "The requested discount"
        claim["claim_type"] = "policy_or_requirement"
        claim["source_requirement"] = "rag"
    elif mutation == "partial_scope":
        text = f"{subject} is confirmed for every reporting period."
        claim["claim_type"] = "business_status"
    else:
        text = text
    claim["text"] = text
    claim["source_text"] = text
    claim["source_span"] = {"start": 0, "end": len(text)}
    claim["claim_id"] = stable_id(
        "cal_claim", "adversarial", source["case"]["claim_id"], index, text
    )
    claim["ordinal"] = 1
    validate_claim(claim)
    pair["case"].update(
        {
            "case_id": stable_id("case", claim["claim_id"]),
            "claim_id": claim["claim_id"],
            "source_group": "adversarial",
            "mutation_type": mutation,
            "final_answer": text,
        }
    )
    pair["proposal"] = _judge_case(pair["case"])
    return pair


def _failure_case(source: dict[str, Any], index: int) -> dict[str, Any]:
    pair = copy.deepcopy(source)
    claim = pair["case"]["claim"]
    claim["claim_id"] = stable_id("cal_claim", "tool_failure", source["case"]["claim_id"], index)
    failure_type = "tool_error" if index % 2 == 0 else "empty_result"
    content = (
        "SQL query timed out."
        if failure_type == "tool_error"
        else "Retrieval returned no documents."
    )
    evidence = {
        "schema_version": SCHEMA_VERSION,
        "evidence_id": stable_id("evidence", claim["run_id"], "failure", index),
        "run_id": claim["run_id"],
        "task_id": claim["task_id"],
        "source_type": failure_type,
        "tool": "sql_query" if index % 2 == 0 else "rag_search",
        "tool_step": 99,
        "content": content,
        "structured_payload": {},
        "provenance": {"trace_run_id": claim["run_id"], "event_step": 99, "item_index": 0},
    }
    validate_evidence(evidence)
    pair["case"].update(
        {
            "case_id": stable_id("case", claim["claim_id"]),
            "claim_id": claim["claim_id"],
            "source_group": "tool_failure",
            "failure_type": failure_type,
            "evidence": [evidence],
        }
    )
    pair["proposal"] = _judge_case(pair["case"])
    return pair


def _judge_case(case: dict[str, Any]) -> dict[str, Any]:
    claim = case["claim"]
    candidates, selection = EvidenceSelector(limit=8).select(claim, case["evidence"])
    task = {"id": case["task_id"], "task_type": case["task_type"]}
    verdict, _ = CompositeClaimJudge(RuleOnlyJudgeProvider()).judge(
        claim,
        candidates,
        task,
        selection,
    )
    return verdict


def _assign_splits(pairs: list[dict[str, Any]]) -> None:
    split_pattern = ("development", "development", "development", "calibration", "held_out")
    for index, pair in enumerate(pairs):
        pair["case"]["split"] = split_pattern[index % len(split_pattern)]


def _protect_human_work(output: Path) -> None:
    if (output / "gold.jsonl").exists():
        raise ValueError("refusing to rebuild a dataset that already contains gold.jsonl")
    annotations = output / "annotations"
    if annotations.exists() and any(path.stat().st_size for path in annotations.glob("*.jsonl")):
        raise ValueError("refusing to rebuild a dataset that contains human annotations")
