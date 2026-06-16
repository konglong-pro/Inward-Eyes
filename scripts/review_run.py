from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.io import write_json, write_text
from inward_eyes.review import build_run_review, render_run_review_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a local review checklist for one run directory.")
    parser.add_argument("run_dir")
    parser.add_argument("--output", help="Optional Markdown output path. Defaults to <run_dir>/review/review.md.")
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    if not run_dir.exists():
        raise SystemExit(f"run_dir does not exist: {run_dir}")
    review = build_run_review(run_dir)
    output_path = Path(args.output).resolve() if args.output else run_dir / "review" / "review.md"
    write_json(output_path.with_suffix(".json"), review)
    write_text(output_path, render_run_review_markdown(review))
    print(output_path)
    return 0 if review["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
