from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.io import write_json, write_text
from inward_eyes.run_index import find_canonical_run_ancestor
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
    output_path = Path(os.path.abspath(args.output)) if args.output else run_dir / "review" / "review.md"
    if output_path.suffix.lower() == ".json":
        raise SystemExit("review Markdown output must not use a .json path")
    json_output_path = output_path.with_suffix(".json")
    for target in (output_path, json_output_path):
        try:
            output_relative = target.relative_to(run_dir)
        except ValueError:
            output_relative = None
        if output_relative is not None:
            if not output_relative.parts or output_relative.parts[0] != "review":
                raise SystemExit("review output inside a run must stay under the derived review/ directory")
            current = run_dir
            for part in output_relative.parts:
                current = current / part
                if current.is_symlink():
                    raise SystemExit(f"review output path must not traverse a symlink inside the reviewed run: {current}")
            try:
                target.resolve(strict=False).relative_to(run_dir / "review")
            except ValueError as exc:
                raise SystemExit("review output path resolves outside the reviewed run review/ directory") from exc
        run_ancestor = find_canonical_run_ancestor(target)
        if run_ancestor is not None and run_ancestor.resolve() != run_dir:
            raise SystemExit(f"review output must not modify another canonical run: {run_ancestor}")
    write_json(json_output_path, review)
    write_text(output_path, render_run_review_markdown(review))
    print(output_path)
    return 0 if review["review_status"] == "pass" else 2 if review["review_status"] == "review_required" else 1


if __name__ == "__main__":
    raise SystemExit(main())
