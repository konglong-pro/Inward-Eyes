from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.io import read_json, write_text
from inward_eyes.markdown import render_page_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Render page.md from metadata.json and document_ast.json.")
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--document-ast", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    metadata = read_json(Path(args.metadata))
    ast = read_json(Path(args.document_ast))
    write_text(Path(args.output), render_page_markdown(metadata, ast))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

