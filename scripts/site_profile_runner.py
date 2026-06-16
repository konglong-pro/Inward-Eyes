from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.io import utc_now, write_json, write_text
from inward_eyes.site_profiles import (
    load_site_profiles,
    match_site_profile,
    render_site_profile_markdown,
    validate_site_profiles,
)


def _slug_timestamp(timestamp: str) -> str:
    return re.sub(r"[^0-9TZ]", "", timestamp)


def run(args: argparse.Namespace) -> Path:
    started_at = utc_now()
    run_id = args.run_id or f"{_slug_timestamp(started_at)}-site-profiles"
    output_root = Path(args.output_root or "browser-operator-runs").resolve()
    run_dir = output_root / run_id
    profile_path = Path(args.profile_file).resolve() if args.profile_file else None
    profiles = load_site_profiles(profile_path)
    report = validate_site_profiles(profiles)
    match = None
    if args.url:
        match = match_site_profile(profiles, url=args.url, page_type=args.page_type, site_name=args.site_name)

    write_json(run_dir / "input.json", {"profile_file": str(profile_path) if profile_path else "default", "url": args.url})
    write_json(run_dir / "artifacts" / "site-profiles.json", profiles)
    write_text(run_dir / "artifacts" / "site-profiles.md", render_site_profile_markdown(profiles, report))
    if match:
        write_json(run_dir / "artifacts" / "site-profile-match.json", match)
    write_json(run_dir / "validation" / "site-profile-report.json", report)
    artifacts = [
        {"id": "A001", "type": "site_profiles", "path": "artifacts/site-profiles.json"},
        {"id": "A002", "type": "markdown_report", "path": "artifacts/site-profiles.md"},
    ]
    if match:
        artifacts.append({"id": "A003", "type": "site_profile_match", "path": "artifacts/site-profile-match.json"})
    write_json(
        run_dir / "manifest.json",
        {
            "run_id": run_id,
            "task": "site-profiles",
            "started_at": started_at,
            "finished_at": utc_now(),
            "operator": "codex",
            "skill": "internal",
            "inputs": {"profile_file": str(profile_path) if profile_path else "default", "url": args.url},
            "artifacts": artifacts,
            "evidence": [{"id": "V001", "type": "validation_report", "path": "validation/site-profile-report.json"}],
            "validation": {
                "schema_valid": report["status"] == "pass",
                "warnings": len(report["warnings"]),
                "requires_manual_review": bool(report["requires_manual_review"]),
                "report_path": "validation/site-profile-report.json",
            },
            "warnings": report["warnings"],
            "requires_manual_review": bool(report["requires_manual_review"]),
            "run_status": report["run_status"],
            "validation_status": report["validation_status"],
            "manual_review": report["manual_review"],
            "completion_blockers": report["completion_blockers"],
            "screenshot_policy": {"required": False, "reason": "site_profile_catalog", "status": "not_required"},
        },
    )
    print(run_dir)
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate site profiles and optionally match one URL.")
    parser.add_argument("--profile-file")
    parser.add_argument("--url")
    parser.add_argument("--page-type", default="unknown")
    parser.add_argument("--site-name")
    parser.add_argument("--output-root", default="browser-operator-runs")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    run_dir = run(args)
    report = (run_dir / "validation" / "site-profile-report.json").read_text(encoding="utf-8")
    return 0 if '"status": "pass"' in report else 1


if __name__ == "__main__":
    raise SystemExit(main())
