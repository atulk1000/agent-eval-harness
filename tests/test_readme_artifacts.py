import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_RUNS = ROOT / "examples" / "sample_runs"


class ReadmeArtifactTests(unittest.TestCase):
    def test_sample_results_table_matches_summary_artifacts(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for artifact_name in ("baseline_summary.json", "improved_summary.json"):
            summary = json.loads((SAMPLE_RUNS / artifact_name).read_text(encoding="utf-8"))
            expected_row = (
                f"| `{summary['agent_name']}` | {summary['overall_score']:.3f} | "
                f"{summary['passed']} | {summary['failed']} | "
                f"{summary['unsupported_claim_count']} | "
                f"{summary['high_severity_claim_count']} |"
            )

            self.assertIn(expected_row, readme, f"README metrics drifted from {artifact_name}")


if __name__ == "__main__":
    unittest.main()
