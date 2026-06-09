from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.io import write_json
from inward_eyes.validation import validate_page_to_md_run


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a page-to-md run directory.")
    parser.add_argument("run_dir")
    parser.add_argument("--write", action="store_true", help="Write validation/validation-report.json.")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    report = validate_page_to_md_run(run_dir)
    if args.write:
        write_json(run_dir / "validation" / "validation-report.json", report)
    else:
        import json

        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

