from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.io import utc_now, write_json, write_text
from inward_eyes.privacy import build_privacy_report, render_privacy_markdown


def _slug_timestamp(timestamp: str) -> str:
    return re.sub(r"[^0-9TZ]", "", timestamp)


def run(args: argparse.Namespace) -> Path:
    target = Path(args.target).resolve()
    if not target.exists():
        raise SystemExit(f"target does not exist: {target}")
    started_at = utc_now()
    run_id = args.run_id or f"{_slug_timestamp(started_at)}-privacy-report"
    output_root = Path(args.output_root or "browser-operator-runs").resolve()
    run_dir = output_root / run_id
    report = build_privacy_report(target)
    write_json(run_dir / "input.json", {"target": str(target)})
    write_json(run_dir / "artifacts" / "privacy-report.json", report)
    write_text(run_dir / "artifacts" / "privacy-report.md", render_privacy_markdown(report))
    write_json(run_dir / "validation" / "privacy-validation-report.json", report)
    write_json(
        run_dir / "manifest.json",
        {
            "run_id": run_id,
            "task": "privacy-report",
            "started_at": started_at,
            "finished_at": utc_now(),
            "operator": "codex",
            "skill": "internal",
            "inputs": {"target": str(target)},
            "artifacts": [
                {"id": "A001", "type": "privacy_report", "path": "artifacts/privacy-report.json"},
                {"id": "A002", "type": "markdown_report", "path": "artifacts/privacy-report.md"},
            ],
            "evidence": [{"id": "V001", "type": "validation_report", "path": "validation/privacy-validation-report.json"}],
            "validation": {
                "schema_valid": report["status"] == "pass",
                "warnings": len(report["warnings"]),
                "requires_manual_review": bool(report["requires_manual_review"]),
                "report_path": "validation/privacy-validation-report.json",
            },
            "warnings": report["warnings"],
            "requires_manual_review": bool(report["requires_manual_review"]),
            "run_status": report["run_status"],
            "validation_status": report["validation_status"],
            "manual_review": report["manual_review"],
            "completion_blockers": report["completion_blockers"],
            "screenshot_policy": {"required": False, "reason": "privacy_scan", "status": "not_required"},
        },
    )
    print(run_dir)
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan a run directory or artifact for privacy findings.")
    parser.add_argument("target")
    parser.add_argument("--output-root", default="browser-operator-runs")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    run_dir = run(args)
    report = (run_dir / "validation" / "privacy-validation-report.json").read_text(encoding="utf-8")
    return 0 if '"status": "pass"' in report else 1


if __name__ == "__main__":
    raise SystemExit(main())
