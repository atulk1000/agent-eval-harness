"""Calibration metrics, confidence intervals, slices, and release gates."""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agenteval.claim_eval.annotations import load_annotations
from agenteval.claim_eval.models import VERDICTS
from agenteval.trace import read_jsonl, write_json

LABELS = sorted(VERDICTS)
UNSUPPORTED_LABELS = {"unsupported", "contradicted"}
GATES = {
    "claim_extraction_recall": (0.90, ">="),
    "claim_extraction_precision": (0.85, ">="),
    "verdict_macro_f1": (0.80, ">="),
    "unsupported_contradicted_recall": (0.90, ">="),
    "evidence_reference_f1": (0.80, ">="),
    "high_severity_false_negatives": (0, "=="),
    "structured_output_validity": (0.98, ">="),
    "cohen_kappa": (0.75, ">="),
}


def run_calibration(dataset_dir: str | Path, output_dir: str | Path) -> dict[str, Any]:
    dataset = Path(dataset_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    cases = read_jsonl(dataset / "cases.jsonl")
    proposals = read_jsonl(dataset / "proposals.jsonl")
    gold_path = dataset / "gold.jsonl"
    gold = read_jsonl(gold_path) if gold_path.exists() else []
    annotations_dir = dataset / "annotations"
    annotations = load_annotations(annotations_dir) if annotations_dir.exists() else []

    report = calibration_report(cases, proposals, gold, annotations)
    write_json(output / "calibration_report.json", report)
    return report


def calibration_report(
    cases: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
    gold: list[dict[str, Any]],
    annotations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    proposal_by_id = {row["claim_id"]: row for row in proposals}
    gold_by_id = {row["claim_id"]: row for row in gold}
    paired_cases = [
        case
        for case in cases
        if case["claim_id"] in proposal_by_id and case["claim_id"] in gold_by_id
    ]
    base = {
        "schema_version": "1.0",
        "status": "pending_human_review",
        "case_count": len(cases),
        "proposal_count": len(proposals),
        "gold_count": len(gold),
        "paired_count": len(paired_cases),
        "limitations": [],
    }
    if not gold:
        base["limitations"].append("No adjudicated human gold labels are available.")
        base["gates"] = {name: {"status": "not_evaluated"} for name in GATES}
        return base

    y_true = [gold_by_id[case["claim_id"]]["verdict"] for case in paired_cases]
    y_pred = [proposal_by_id[case["claim_id"]]["verdict"] for case in paired_cases]
    classification = classification_metrics(y_true, y_pred)
    evidence = evidence_reference_metrics(paired_cases, proposal_by_id, gold_by_id)
    extraction = extraction_metrics(cases, proposal_by_id, gold_by_id)
    severity = severity_metrics(paired_cases, proposal_by_id, gold_by_id)
    validity = sum(1 for proposal in proposals if _valid_proposal(proposal)) / max(
        len(proposals), 1
    )
    human_labels = reviewer_agreement(annotations or [])
    kappa = human_labels["cohen_kappa"]
    unsupported = _binary_metrics(y_true, y_pred, UNSUPPORTED_LABELS)
    valid_count = sum(1 for proposal in proposals if _valid_proposal(proposal))
    repeat_pairs = [
        proposal for proposal in proposals if proposal.get("repeat_verdict") is not None
    ]
    reliability = {
        "judge_error_count": len(proposals) - valid_count,
        "judge_error_rate": _ratio(len(proposals) - valid_count, len(proposals)),
        "abstention_count": sum(
            proposal.get("verdict") == "not_enough_evidence" for proposal in proposals
        ),
        "abstention_rate": _ratio(
            sum(proposal.get("verdict") == "not_enough_evidence" for proposal in proposals),
            len(proposals),
        ),
        "repeat_agreement": (
            _ratio(
                sum(
                    proposal.get("repeat_verdict") == proposal.get("verdict")
                    for proposal in repeat_pairs
                ),
                len(repeat_pairs),
            )
            if repeat_pairs
            else None
        ),
        "repeat_pair_count": len(repeat_pairs),
    }
    values = {
        "claim_extraction_recall": extraction["recall"],
        "claim_extraction_precision": extraction["precision"],
        "verdict_macro_f1": classification["macro_f1"],
        "unsupported_contradicted_recall": unsupported["recall"],
        "evidence_reference_f1": evidence["f1"],
        "high_severity_false_negatives": severity["high_severity_false_negatives"],
        "structured_output_validity": validity,
        "cohen_kappa": kappa,
    }
    gates = _evaluate_gates(values)
    complete = len(paired_cases) == len(cases) and kappa is not None
    passed = complete and all(item["status"] == "pass" for item in gates.values())
    base.update(
        {
            "status": "passed" if passed else ("failed" if complete else "incomplete"),
            "claim_extraction": extraction,
            "verdict_classification": classification,
            "unsupported_claims": unsupported,
            "evidence_references": evidence,
            "severity": severity,
            "structured_output_validity": validity,
            "reliability": reliability,
            "human_labels": human_labels,
            "cohen_kappa": kappa,
            "slices": slice_metrics(paired_cases, proposal_by_id, gold_by_id),
            "bootstrap_confidence_intervals": {
                "verdict_macro_f1": bootstrap_interval(y_true, y_pred, _macro_f1),
                "unsupported_contradicted_recall": bootstrap_interval(
                    y_true,
                    y_pred,
                    lambda truth, pred: _binary_recall(truth, pred, UNSUPPORTED_LABELS),
                ),
            },
            "gates": gates,
        }
    )
    if len(paired_cases) != len(cases):
        base["limitations"].append("Human gold coverage is incomplete.")
    if kappa is None:
        base["limitations"].append(
            "Independent held-out review is unavailable; agreement is not claimed."
        )
    return base


def classification_metrics(y_true: list[str], y_pred: list[str]) -> dict[str, Any]:
    matrix = {actual: {predicted: 0 for predicted in LABELS} for actual in LABELS}
    for actual, predicted in zip(y_true, y_pred, strict=True):
        matrix[actual][predicted] += 1
    per_verdict: dict[str, dict[str, Any]] = {}
    for label in LABELS:
        tp = matrix[label][label]
        fp = sum(matrix[actual][label] for actual in LABELS if actual != label)
        fn = sum(matrix[label][predicted] for predicted in LABELS if predicted != label)
        precision = _ratio(tp, tp + fp)
        recall = _ratio(tp, tp + fn)
        per_verdict[label] = {
            "support": sum(matrix[label].values()),
            "precision": precision,
            "recall": recall,
            "f1": _f1(precision, recall),
        }
    return {
        "count": len(y_true),
        "accuracy": _ratio(sum(matrix[label][label] for label in LABELS), len(y_true)),
        "macro_f1": _ratio(sum(item["f1"] for item in per_verdict.values()), len(LABELS)),
        "per_verdict": per_verdict,
        "confusion_matrix": matrix,
    }


def extraction_metrics(
    cases: list[dict[str, Any]],
    proposals: dict[str, dict[str, Any]],
    gold: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    expected = sum(1 for case in cases if gold.get(case["claim_id"], {}).get("claim_valid", True))
    predicted = len(proposals)
    matched = sum(1 for case in cases if case["claim_id"] in proposals and case["claim_id"] in gold)
    precision = _ratio(matched, predicted)
    recall = _ratio(matched, expected)
    atomicity_errors = sum(1 for row in gold.values() if row.get("atomicity_error", False))
    return {
        "expected_count": expected,
        "predicted_count": predicted,
        "matched_count": matched,
        "precision": precision,
        "recall": recall,
        "f1": _f1(precision, recall),
        "atomicity_error_rate": _ratio(atomicity_errors, max(expected, 1)),
    }


def evidence_reference_metrics(
    cases: list[dict[str, Any]],
    proposals: dict[str, dict[str, Any]],
    gold: dict[str, dict[str, Any]],
) -> dict[str, float]:
    tp = fp = fn = 0
    for case in cases:
        claim_id = case["claim_id"]
        predicted = set(proposals[claim_id].get("evidence_refs", []))
        expected = set(gold[claim_id].get("evidence_refs", []))
        tp += len(predicted & expected)
        fp += len(predicted - expected)
        fn += len(expected - predicted)
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    return {
        "true_positive_count": tp,
        "false_positive_count": fp,
        "false_negative_count": fn,
        "precision": precision,
        "recall": recall,
        "f1": _f1(precision, recall),
    }


def severity_metrics(
    cases: list[dict[str, Any]],
    proposals: dict[str, dict[str, Any]],
    gold: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    weights = {"none": 1, "low": 1, "medium": 2, "high": 4}
    correct_weight = total_weight = 0
    high_misses = 0
    for case in cases:
        claim_id = case["claim_id"]
        expected = gold[claim_id].get("severity", "none")
        predicted = proposals[claim_id].get("severity", "none")
        weight = weights[expected]
        total_weight += weight
        correct_weight += weight if expected == predicted else 0
        if expected == "high" and predicted != "high":
            high_misses += 1
    return {
        "weighted_accuracy": _ratio(correct_weight, total_weight),
        "high_severity_false_negatives": high_misses,
    }


def reviewer_kappa(annotations: list[dict[str, Any]]) -> float | None:
    return reviewer_agreement(annotations)["cohen_kappa"]


def reviewer_agreement(annotations: list[dict[str, Any]]) -> dict[str, Any]:
    by_claim: dict[str, dict[str, str]] = defaultdict(dict)
    for annotation in annotations:
        if annotation.get("review_stage") in {"primary", "independent"}:
            by_claim[annotation["claim_id"]][annotation["reviewer_id"]] = annotation["verdict"]
    pairs = []
    for labels in by_claim.values():
        if len(labels) >= 2:
            pairs.append(list(sorted(labels.items()))[:2])
    if not pairs:
        return {"independent_pair_count": 0, "raw_agreement": None, "cohen_kappa": None}
    first = [pair[0][1] for pair in pairs]
    second = [pair[1][1] for pair in pairs]
    observed = sum(left == right for left, right in zip(first, second, strict=True)) / len(pairs)
    first_counts = Counter(first)
    second_counts = Counter(second)
    expected = sum(
        first_counts[label] / len(pairs) * second_counts[label] / len(pairs) for label in LABELS
    )
    kappa = round((observed - expected) / (1 - expected), 3) if expected < 1 else 1.0
    return {
        "independent_pair_count": len(pairs),
        "raw_agreement": round(observed, 3),
        "cohen_kappa": kappa,
    }


def slice_metrics(
    cases: list[dict[str, Any]],
    proposals: dict[str, dict[str, Any]],
    gold: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        grouped[str(case.get("task_type", "unknown"))].append(case)
    task_type_result = {}
    for name, rows in sorted(grouped.items()):
        truth = [gold[row["claim_id"]]["verdict"] for row in rows]
        predicted = [proposals[row["claim_id"]]["verdict"] for row in rows]
        task_type_result[name] = {
            "count": len(rows),
            "macro_f1": classification_metrics(truth, predicted)["macro_f1"],
        }
    path_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        path = str(proposals[case["claim_id"]].get("judge_path", "unknown"))
        path_groups[path].append(case)
    judgment_path_result = {}
    for name, rows in sorted(path_groups.items()):
        truth = [gold[row["claim_id"]]["verdict"] for row in rows]
        predicted = [proposals[row["claim_id"]]["verdict"] for row in rows]
        judgment_path_result[name] = {
            "count": len(rows),
            "macro_f1": classification_metrics(truth, predicted)["macro_f1"],
        }
    return {"task_type": task_type_result, "judge_path": judgment_path_result}


def bootstrap_interval(
    y_true: list[str],
    y_pred: list[str],
    metric: Callable[[list[str], list[str]], float],
    *,
    samples: int = 500,
    seed: int = 13,
) -> dict[str, float] | None:
    if not y_true:
        return None
    randomizer = random.Random(seed)
    values = []
    for _ in range(samples):
        indexes = [randomizer.randrange(len(y_true)) for _ in y_true]
        values.append(metric([y_true[i] for i in indexes], [y_pred[i] for i in indexes]))
    values.sort()
    return {
        "lower_95": round(values[int(samples * 0.025)], 3),
        "upper_95": round(values[min(samples - 1, int(samples * 0.975))], 3),
    }


def _evaluate_gates(values: dict[str, float | int | None]) -> dict[str, Any]:
    gates = {}
    for name, (threshold, operator) in GATES.items():
        value = values[name]
        if value is None:
            gates[name] = {"status": "not_evaluated", "threshold": threshold, "value": None}
            continue
        passed = value >= threshold if operator == ">=" else value == threshold
        gates[name] = {
            "status": "pass" if passed else "fail",
            "threshold": threshold,
            "operator": operator,
            "value": value,
        }
    return gates


def _valid_proposal(proposal: dict[str, Any]) -> bool:
    return (
        proposal.get("verdict") in VERDICTS
        and isinstance(proposal.get("confidence"), (int, float))
        and isinstance(proposal.get("reason"), str)
        and bool(proposal["reason"].strip())
        and isinstance(proposal.get("evidence_refs"), list)
    )


def _binary_recall(y_true: list[str], y_pred: list[str], positive: set[str]) -> float:
    return _binary_metrics(y_true, y_pred, positive)["recall"]


def _binary_metrics(y_true: list[str], y_pred: list[str], positive: set[str]) -> dict[str, Any]:
    positives = sum(label in positive for label in y_true)
    true_positives = sum(
        actual in positive and predicted in positive
        for actual, predicted in zip(y_true, y_pred, strict=True)
    )
    predicted_positives = sum(label in positive for label in y_pred)
    precision = _ratio(true_positives, predicted_positives)
    recall = _ratio(true_positives, positives)
    return {
        "gold_positive_count": positives,
        "predicted_positive_count": predicted_positives,
        "true_positive_count": true_positives,
        "precision": precision,
        "recall": recall,
        "f1": _f1(precision, recall),
    }


def _macro_f1(y_true: list[str], y_pred: list[str]) -> float:
    return classification_metrics(y_true, y_pred)["macro_f1"]


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return round(numerator / denominator, 3) if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return round(2 * precision * recall / (precision + recall), 3) if precision + recall else 0.0
