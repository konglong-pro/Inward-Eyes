from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.distribution import validate_plugin_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Codex plugin without machine-specific tooling.")
    parser.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parents[2]))
    args = parser.parse_args()
    report = validate_plugin_manifest(Path(args.root).resolve())
    if report["status"] != "pass":
        print("FAIL")
        for error in report["errors"]:
            print(f"- {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
