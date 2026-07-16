from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.run_index import find_canonical_run_ancestor, write_retry_plan, write_run_index


def _derived_output_path(raw_path: str) -> Path:
    output_path = Path(raw_path).resolve()
    run_ancestor = find_canonical_run_ancestor(output_path)
    if run_ancestor is not None:
        raise SystemExit(f"derived run-database output must not be written inside canonical run: {run_ancestor}")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Maintain a local JSONL run index and retry plan.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    index_parser = subparsers.add_parser("index")
    index_parser.add_argument("--output-root", default="browser-operator-runs")
    index_parser.add_argument("--index", default="browser-operator-runs/run-index.jsonl")
    retry_parser = subparsers.add_parser("retry-plan")
    retry_parser.add_argument("--index", required=True)
    retry_parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if args.command == "index":
        records = write_run_index(Path(args.output_root).resolve(), _derived_output_path(args.index))
        print(f"{len(records)} runs indexed")
        return 0
    if args.command == "retry-plan":
        records = [
            json.loads(line)
            for line in Path(args.index).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        plan = write_retry_plan(records, _derived_output_path(args.output))
        print(f"{len(plan['retryable_runs'])} retryable runs")
        return 0
    raise SystemExit("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
