from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.adapter_matrix import build_adapter_matrix, render_adapter_matrix_markdown, validate_adapter_matrix
from inward_eyes.io import utc_now, write_json, write_text
from inward_eyes.paths import prepare_run_dir


def _slug_timestamp(timestamp: str) -> str:
    return re.sub(r"[^0-9TZ]", "", timestamp)


def run(args: argparse.Namespace) -> Path:
    root = Path(__file__).resolve().parents[1]
    started_at = utc_now()
    run_id = args.run_id or f"{_slug_timestamp(started_at)}-adapter-matrix"
    matrix = build_adapter_matrix(root)
    report = validate_adapter_matrix(matrix)
    run_dir = prepare_run_dir(args.output_root or "browser-operator-runs", run_id)

    write_json(run_dir / "input.json", {"root": str(root), "phase": "M12"})
    write_json(run_dir / "artifacts" / "adapter-matrix.json", matrix)
    write_text(run_dir / "artifacts" / "adapter-matrix.md", render_adapter_matrix_markdown(matrix, report))
    write_json(run_dir / "validation" / "adapter-matrix-report.json", report)
    write_json(
        run_dir / "manifest.json",
        {
            "run_id": run_id,
            "task": "adapter-matrix",
            "started_at": started_at,
            "finished_at": utc_now(),
            "operator": "codex",
            "skill": "internal",
            "inputs": {"root": str(root)},
            "artifacts": [
                {"id": "A001", "type": "adapter_matrix", "path": "artifacts/adapter-matrix.json"},
                {"id": "A002", "type": "markdown_report", "path": "artifacts/adapter-matrix.md"},
            ],
            "evidence": [{"id": "V001", "type": "validation_report", "path": "validation/adapter-matrix-report.json"}],
            "validation": {
                "schema_valid": report["status"] == "pass",
                "warnings": len(report["warnings"]),
                "requires_manual_review": bool(report["requires_manual_review"]),
                "report_path": "validation/adapter-matrix-report.json",
            },
            "warnings": report["warnings"],
            "requires_manual_review": bool(report["requires_manual_review"]),
            "run_status": report["run_status"],
            "validation_status": report["validation_status"],
            "manual_review": report["manual_review"],
            "completion_blockers": report["completion_blockers"],
            "screenshot_policy": {"required": False, "reason": "adapter_inventory", "status": "not_required"},
        },
    )
    print(run_dir)
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and validate the deterministic adapter matrix.")
    parser.add_argument("--output-root", default="browser-operator-runs")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    run_dir = run(args)
    report = (run_dir / "validation" / "adapter-matrix-report.json").read_text(encoding="utf-8")
    return 0 if '"status": "pass"' in report else 1


if __name__ == "__main__":
    raise SystemExit(main())
