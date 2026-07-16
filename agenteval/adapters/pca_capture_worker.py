"""Standalone PCA capture worker; intentionally depends only on the standard library."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pca-repo", required=True)
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    pca_repo = Path(args.pca_repo).resolve()
    sys.path.insert(0, str(pca_repo))
    from agent.hybrid_tool import answer_question

    benchmark = json.loads(Path(args.benchmark).read_text(encoding="utf-8"))
    revision = _git_revision(pca_repo)
    rows = []
    for task in benchmark["tasks"]:
        captured_at = datetime.now(UTC).replace(microsecond=0).isoformat()
        response = answer_question(
            task["prompt"],
            live_analysis=bool(task.get("metadata", {}).get("pca_live_analysis", False)),
            return_trace=True,
        )
        rows.append(
            {
                "task_id": task["id"],
                "prompt": task["prompt"],
                "captured_at": captured_at,
                "source_revision": revision,
                "response": response,
            }
        )

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    return 0


def _git_revision(repo: Path) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


if __name__ == "__main__":
    raise SystemExit(main())
