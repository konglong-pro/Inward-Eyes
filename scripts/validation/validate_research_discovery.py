from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.discovery import validate_research_discovery_run
from inward_eyes.io import write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a browser-research discovery run directory.")
    parser.add_argument("run_dir")
    parser.add_argument("--write", action="store_true", help="Write validation/discovery-validation-report.json.")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    report = validate_research_discovery_run(run_dir)
    if args.write:
        write_json(run_dir / "validation" / "discovery-validation-report.json", report)
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
