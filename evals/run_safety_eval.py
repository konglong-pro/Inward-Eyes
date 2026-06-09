from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.safety import classify_action


def main() -> int:
    cases = json.loads((ROOT / "evals" / "fixtures" / "safety-actions" / "cases.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    for case in cases:
        decision = classify_action(case["action"])
        if decision.classification != case["classification"]:
            errors.append(f"{case['action']}: classification {decision.classification!r}")
        if decision.allowed is not case["allowed"]:
            errors.append(f"{case['action']}: allowed {decision.allowed!r}")
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

