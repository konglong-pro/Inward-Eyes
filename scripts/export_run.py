from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.exporters import export_run


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a run summary as JSON, CSV, and Markdown.")
    parser.add_argument("run_dir")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    if not (run_dir / "manifest.json").exists():
        raise SystemExit(f"manifest.json missing in {run_dir}")
    output_dir = Path(args.output_dir).resolve() if args.output_dir else run_dir / "exports"
    paths = export_run(run_dir, output_dir)
    print(paths["markdown"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
