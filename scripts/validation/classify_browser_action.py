from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.safety import classify_action


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify a browser action under the Inward Eyes safety contract.")
    parser.add_argument("action")
    args = parser.parse_args()
    decision = classify_action(args.action)
    print(json.dumps(decision.__dict__, ensure_ascii=False, indent=2))
    return 0 if decision.allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())

