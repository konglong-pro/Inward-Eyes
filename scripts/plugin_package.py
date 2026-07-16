from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.distribution import build_distribution_package


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local plugin zip and package manifest.")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--output-dir", default="dist")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output_dir = Path(args.output_dir).resolve()
    package_manifest = build_distribution_package(root, output_dir)
    if package_manifest["validation"]["status"] != "pass":
        for error in package_manifest["validation"]["errors"]:
            print(error, file=sys.stderr)
        print(output_dir / "package-manifest.json")
        return 1
    print(output_dir / package_manifest["package"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
