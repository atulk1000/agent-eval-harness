import tempfile
import unittest
from pathlib import Path

from agenteval.claim_eval.annotations import (
    adjudicate_annotations,
    create_annotation,
)
from agenteval.claim_eval.calibration import build_calibration_dataset
from agenteval.claim_eval.metrics import (
    bootstrap_interval,
    calibration_report,
    classification_metrics,
    reviewer_kappa,
)
from agenteval.trace import read_json, read_jsonl, write_jsonl

ROOT = Path(__file__).resolve().parents[1]


class AnnotationTests(unittest.TestCase):
    def test_create_annotation_records_review_stage(self):
        annotation = _annotation("claim_1", "reviewer_a", split="development")
        self.assertEqual(annotation["review_stage"], "primary")

    def test_primary_review_can_create_nonheldout_gold(self):
        report, gold = _adjudicate([_annotation("claim_1", "reviewer_a", split="development")])
        self.assertEqual(report["gold_count"], 1)
        self.assertEqual(gold[0]["label_source"], "primary_review")

    def test_heldout_requires_independent_review(self):
        report, _ = _adjudicate([_annotation("claim_1", "reviewer_a", split="held_out")])
        self.assertEqual(report["unresolved_count"], 1)

    def test_heldout_agreement_creates_gold(self):
        annotations = [
            _annotation("claim_1", "reviewer_a", split="held_out"),
            _annotation("claim_1", "reviewer_b", split="held_out", stage="independent"),
        ]
        report, gold = _adjudicate(annotations)
        self.assertTrue(report["complete"])
        self.assertEqual(gold[0]["label_source"], "independent_agreement")

    def test_disagreement_remains_unresolved(self):
        annotations = [
            _annotation("claim_1", "reviewer_a", split="held_out"),
            _annotation(
                "claim_1",
                "reviewer_b",
                split="held_out",
                stage="independent",
                verdict="unsupported",
                severity="high",
            ),
        ]
        report, _ = _adjudicate(annotations)
        self.assertEqual(report["unresolved_count"], 1)

    def test_adjudicator_resolves_disagreement(self):
        annotations = [
            _annotation("claim_1", "reviewer_a", split="held_out"),
            _annotation(
                "claim_1",
                "reviewer_b",
                split="held_out",
                stage="independent",
                verdict="unsupported",
                severity="high",
            ),
            _annotation(
                "claim_1",
                "reviewer_c",
                split="held_out",
                stage="adjudicator",
                verdict="unsupported",
                severity="high",
            ),
        ]
        report, gold = _adjudicate(annotations)
        self.assertEqual(report["unresolved_count"], 0)
        self.assertEqual(gold[0]["label_source"], "adjudicator")


class CalibrationMetricTests(unittest.TestCase):
    def test_classification_metrics_builds_confusion_matrix(self):
        metrics = classification_metrics(
            ["supported", "unsupported"],
            ["supported", "contradicted"],
        )
        self.assertEqual(metrics["confusion_matrix"]["unsupported"]["contradicted"], 1)

    def test_perfect_independent_labels_have_kappa_one(self):
        annotations = [
            _annotation("claim_1", "reviewer_a", split="held_out"),
            _annotation("claim_1", "reviewer_b", split="held_out", stage="independent"),
            _annotation(
                "claim_2", "reviewer_a", split="held_out", verdict="unsupported", severity="high"
            ),
            _annotation(
                "claim_2",
                "reviewer_b",
                split="held_out",
                stage="independent",
                verdict="unsupported",
                severity="high",
            ),
        ]
        self.assertEqual(reviewer_kappa(annotations), 1.0)

    def test_bootstrap_interval_is_deterministic(self):
        truth = ["supported", "unsupported", "supported"]
        predicted = ["supported", "unsupported", "unsupported"]

        def metric(actual, guessed):
            return sum(left == right for left, right in zip(actual, guessed, strict=True)) / len(
                actual
            )

        self.assertEqual(
            bootstrap_interval(truth, predicted, metric, samples=50),
            bootstrap_interval(truth, predicted, metric, samples=50),
        )

    def test_report_without_gold_is_pending(self):
        report = calibration_report([{"claim_id": "claim_1"}], [], [], [])
        self.assertEqual(report["status"], "pending_human_review")
        self.assertEqual(report["gates"]["verdict_macro_f1"]["status"], "not_evaluated")

    def test_dataset_builder_writes_approved_case_mix(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "dataset"
            second_output = Path(tmp) / "dataset_second"
            manifest = build_calibration_dataset(output, root=ROOT)
            build_calibration_dataset(second_output, root=ROOT)
            cases = read_jsonl(output / "cases.jsonl")
            first_bytes = (output / "cases.jsonl").read_bytes()
            second_bytes = (second_output / "cases.jsonl").read_bytes()
        self.assertEqual(manifest["case_count"], 100)
        self.assertEqual(manifest["source_counts"]["adversarial"], 40)
        self.assertEqual(len(cases), 100)
        self.assertEqual(first_bytes, second_bytes)

    def test_dataset_builder_protects_existing_gold(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "dataset"
            output.mkdir()
            write_jsonl(output / "gold.jsonl", [{"claim_id": "claim_1"}])
            with self.assertRaisesRegex(ValueError, "gold.jsonl"):
                build_calibration_dataset(output, root=ROOT)


def _annotation(
    claim_id,
    reviewer,
    *,
    split,
    stage="primary",
    verdict="supported",
    severity="none",
):
    return create_annotation(
        claim_id=claim_id,
        reviewer_id=reviewer,
        verdict=verdict,
        severity=severity,
        evidence_refs=["evidence_1"],
        rationale="Reviewed against the supplied evidence.",
        dataset_split=split,
        review_stage=stage,
        created_at=f"2026-07-15T00:00:0{0 if reviewer == 'reviewer_a' else 1}+00:00",
    )


def _adjudicate(annotations):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_jsonl(root / "annotations.jsonl", annotations)
        report = adjudicate_annotations(root / "annotations.jsonl", root / "gold.jsonl")
        gold = read_jsonl(root / "gold.jsonl")
        persisted_report = read_json(root / "adjudication_report.json")
    return persisted_report or report, gold


if __name__ == "__main__":
    unittest.main()
