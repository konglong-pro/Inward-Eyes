from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.safety import classify_action
from inward_eyes.paths import CONTINUATION_HANDOFF_PATH, create_continuation_handoff, prepare_run_dir


OUTPUT_ROOT = ROOT / "evals" / ".tmp" / "safety-handoff"


def run_continuation_handoff_cases() -> list[str]:
    errors: list[str] = []
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    run_dir = prepare_run_dir(OUTPUT_ROOT, "handoff-retry")
    input_path = run_dir / "stage" / "input.json"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text("{}\n", encoding="utf-8")
    token = create_continuation_handoff(
        run_dir,
        run_id="handoff-retry",
        from_stage="parent",
        to_stage="child",
        input_path="stage/input.json",
    )

    try:
        prepare_run_dir(
            OUTPUT_ROOT,
            "handoff-retry",
            continue_existing=True,
            continuation_token="wrong-token",
            continuation_stage="child",
            continuation_input_path="stage/input.json",
        )
    except PermissionError:
        pass
    else:
        errors.append("continuation_handoff accepted an invalid token")

    try:
        prepared = prepare_run_dir(
            OUTPUT_ROOT,
            "handoff-retry",
            continue_existing=True,
            continuation_token=token,
            continuation_stage="child",
            continuation_input_path="stage/input.json",
        )
    except Exception as exc:
        errors.append(f"continuation_handoff burned a valid token after an invalid attempt: {exc}")
    else:
        if prepared != run_dir:
            errors.append("continuation_handoff returned the wrong run directory")

    try:
        prepare_run_dir(
            OUTPUT_ROOT,
            "handoff-retry",
            continue_existing=True,
            continuation_token=token,
            continuation_stage="child",
            continuation_input_path="stage/input.json",
        )
    except PermissionError:
        pass
    else:
        errors.append("continuation_handoff allowed a successfully consumed token to be replayed")

    if list(run_dir.glob(".*claimed-*")):
        errors.append("continuation_handoff left a claimed handoff file behind")

    tamper_run_dir = prepare_run_dir(OUTPUT_ROOT, "handoff-authenticated-digest")
    tamper_input_path = tamper_run_dir / "stage" / "input.json"
    tamper_input_path.parent.mkdir(parents=True, exist_ok=True)
    tamper_payload = b'{"approved":true}\n'
    tamper_input_path.write_bytes(tamper_payload)
    artifact_sha256 = {
        "stage/input.json": f"sha256:{hashlib.sha256(tamper_payload).hexdigest()}"
    }
    tamper_token = create_continuation_handoff(
        tamper_run_dir,
        run_id="handoff-authenticated-digest",
        from_stage="parent",
        to_stage="child",
        input_path="stage/input.json",
        artifact_sha256=artifact_sha256,
    )
    marker_path = tamper_run_dir / CONTINUATION_HANDOFF_PATH
    original_marker = marker_path.read_bytes()
    marker = json.loads(original_marker)
    marker["artifact_sha256"]["stage/input.json"] = f"sha256:{'0' * 64}"
    marker_path.write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    try:
        prepare_run_dir(
            OUTPUT_ROOT,
            "handoff-authenticated-digest",
            continue_existing=True,
            continuation_token=tamper_token,
            continuation_stage="child",
            continuation_input_path="stage/input.json",
            continuation_artifact_sha256=marker["artifact_sha256"],
        )
    except PermissionError:
        pass
    else:
        errors.append("continuation_handoff accepted tampered digest metadata with the correct token")
    marker_path.write_bytes(original_marker)
    try:
        prepare_run_dir(
            OUTPUT_ROOT,
            "handoff-authenticated-digest",
            continue_existing=True,
            continuation_token=tamper_token,
            continuation_stage="child",
            continuation_input_path="stage/input.json",
            continuation_artifact_sha256=artifact_sha256,
        )
    except Exception as exc:
        errors.append(f"continuation_handoff could not retry after authenticated marker repair: {exc}")
    try:
        prepare_run_dir(
            OUTPUT_ROOT,
            "handoff-authenticated-digest",
            continue_existing=True,
            continuation_token=tamper_token,
            continuation_stage="child",
            continuation_input_path="stage/input.json",
            continuation_artifact_sha256=artifact_sha256,
        )
    except PermissionError:
        pass
    else:
        errors.append("continuation_handoff replayed a repaired and consumed authenticated handoff")
    return errors


def main() -> int:
    cases = json.loads((ROOT / "evals" / "fixtures" / "safety-actions" / "cases.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    errors.extend(run_continuation_handoff_cases())
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
