from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.capture import validate_page_capture_contract
from inward_eyes.io import read_json, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a page_capture.json against the M6 adapter contract.")
    parser.add_argument("capture_json")
    parser.add_argument("--write-report", help="Optional path for a validation report JSON.")
    args = parser.parse_args()

    capture_path = Path(args.capture_json).resolve()
    report = validate_page_capture_contract(read_json(capture_path))
    if args.write_report:
        write_json(Path(args.write_report).resolve(), report)
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
