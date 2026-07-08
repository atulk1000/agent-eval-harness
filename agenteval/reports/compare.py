"""Run comparison helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agenteval.reports.markdown import render_comparison
from agenteval.trace import read_json, write_json


def compare_run_dirs(left_dir: str | Path, right_dir: str | Path, out_dir: str | Path | None = None) -> dict[str, Any]:
    left_path = Path(left_dir)
    right_path = Path(right_dir)
    left = read_json(left_path / "summary.json")
    right = read_json(right_path / "summary.json")
    dimensions = set(left.get("dimension_averages", {})) | set(right.get("dimension_averages", {}))
    comparison = {
        "left": left,
        "right": right,
        "overall_score_delta": round(right["overall_score"] - left["overall_score"], 3),
        "unsupported_claim_delta": right["unsupported_claim_count"] - left["unsupported_claim_count"],
        "dimension_deltas": {
            dimension: round(
                right.get("dimension_averages", {}).get(dimension, 0.0)
                - left.get("dimension_averages", {}).get(dimension, 0.0),
                3,
            )
            for dimension in sorted(dimensions)
        },
    }
    if out_dir is not None:
        output = Path(out_dir)
        output.mkdir(parents=True, exist_ok=True)
        write_json(output / "comparison.json", comparison)
        (output / "comparison.md").write_text(render_comparison(comparison), encoding="utf-8")
    return comparison
