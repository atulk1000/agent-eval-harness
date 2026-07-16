"""Human annotation records and adjudication."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agenteval.claim_eval.models import (
    SCHEMA_VERSION,
    stable_id,
    validate_annotation,
)
from agenteval.trace import read_jsonl, write_json, write_jsonl


def create_annotation(
    *,
    claim_id: str,
    reviewer_id: str,
    verdict: str,
    severity: str,
    evidence_refs: list[str],
    rationale: str,
    dataset_split: str,
    review_stage: str = "primary",
    created_at: str | None = None,
) -> dict[str, Any]:
    timestamp = created_at or datetime.now(UTC).replace(microsecond=0).isoformat()
    record = {
        "schema_version": SCHEMA_VERSION,
        "annotation_id": stable_id(
            "annotation",
            claim_id,
            reviewer_id,
            review_stage,
            timestamp,
            verdict,
            severity,
            sorted(evidence_refs),
        ),
        "claim_id": claim_id,
        "reviewer_id": reviewer_id,
        "verdict": verdict,
        "severity": severity,
        "evidence_refs": sorted(set(evidence_refs)),
        "rationale": rationale,
        "dataset_split": dataset_split,
        "review_stage": review_stage,
        "created_at": timestamp,
    }
    return validate_annotation(record)


def load_annotations(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    files = sorted(source.rglob("*.jsonl")) if source.is_dir() else [source]
    annotations: list[dict[str, Any]] = []
    for file_path in files:
        for record in read_jsonl(file_path):
            annotations.append(validate_annotation(record))
    return annotations


def adjudicate_annotations(
    annotations_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    annotations = load_annotations(annotations_path)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for annotation in annotations:
        grouped[annotation["claim_id"]].append(annotation)

    gold: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for claim_id, records in sorted(grouped.items()):
        adjudicators = [record for record in records if record.get("review_stage") == "adjudicator"]
        if adjudicators:
            chosen = sorted(adjudicators, key=lambda record: record["created_at"])[-1]
            label_source = "adjudicator"
        else:
            independent = {
                record["reviewer_id"]: record
                for record in records
                if record.get("review_stage") in {"primary", "independent"}
            }
            labels = {
                (record["verdict"], record["severity"], tuple(sorted(record["evidence_refs"])))
                for record in independent.values()
            }
            held_out = any(record.get("dataset_split") == "held_out" for record in records)
            if len(labels) == 1 and (not held_out or len(independent) >= 2):
                chosen = sorted(independent.values(), key=lambda record: record["created_at"])[-1]
                label_source = (
                    "independent_agreement" if len(independent) >= 2 else "primary_review"
                )
            else:
                unresolved.append(
                    {
                        "claim_id": claim_id,
                        "reviewer_count": len(independent),
                        "labels": [list(label) for label in sorted(labels)],
                        "reason": "Held-out review is incomplete or reviewer labels disagree.",
                    }
                )
                continue
        gold.append(
            {
                "schema_version": SCHEMA_VERSION,
                "gold_id": stable_id("gold", claim_id, chosen["verdict"], chosen["severity"]),
                "claim_id": claim_id,
                "verdict": chosen["verdict"],
                "severity": chosen["severity"],
                "evidence_refs": chosen["evidence_refs"],
                "rationale": chosen["rationale"],
                "label_source": label_source,
                "reviewer_count": len({record["reviewer_id"] for record in records}),
            }
        )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(output, gold)
    report = {
        "schema_version": SCHEMA_VERSION,
        "annotation_count": len(annotations),
        "claim_count": len(grouped),
        "gold_count": len(gold),
        "unresolved_count": len(unresolved),
        "unresolved": unresolved,
        "complete": not unresolved and bool(gold),
    }
    write_json(output.with_name("adjudication_report.json"), report)
    return report
