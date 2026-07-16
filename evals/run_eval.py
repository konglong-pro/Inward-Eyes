from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "evals" / "fixtures" / "page-to-md"
OUTPUT_ROOT = ROOT / "evals" / ".tmp" / "page-to-md"
SCREENSHOT_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def load_cases() -> list[dict[str, object]]:
    return json.loads((FIXTURE_ROOT / "cases.json").read_text(encoding="utf-8"))


def run_case(case: dict[str, object]) -> list[str]:
    errors: list[str] = []
    fixture_path = FIXTURE_ROOT / str(case["input"])
    input_path = fixture_path
    if fixture_path.suffix.lower() == ".json":
        case_input_root = OUTPUT_ROOT / "_inputs" / str(case["name"])
        case_input_root.mkdir(parents=True, exist_ok=True)
        input_doc = json.loads(fixture_path.read_text(encoding="utf-8"))
        assets = input_doc.get("assets") if isinstance(input_doc.get("assets"), dict) else {}
        screenshots = assets.get("screenshots") if isinstance(assets.get("screenshots"), list) else []
        for index, item in enumerate(screenshots, start=1):
            screenshot_path = f"screenshots/{index:03d}.png"
            if isinstance(item, str):
                screenshots[index - 1] = screenshot_path
            elif isinstance(item, dict):
                item["path"] = screenshot_path
            destination = case_input_root / Path(screenshot_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(SCREENSHOT_PNG)
        input_path = case_input_root / "input.json"
        input_path.write_text(json.dumps(input_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run_id = f"eval-{case['name']}"
    command = [
        sys.executable,
        str(ROOT / "scripts" / "page_to_md_runner.py"),
        "--input",
        str(input_path),
        "--url",
        str(case["url"]),
        "--output-root",
        str(OUTPUT_ROOT),
        "--run-id",
        run_id,
        "--page-type",
        str(case.get("page_type", "auto")),
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if completed.returncode != 0:
        return [f"{case['name']}: runner failed: {completed.stderr.strip()}"]

    run_dir = OUTPUT_ROOT / run_id
    metadata = json.loads((run_dir / "artifacts" / "metadata.json").read_text(encoding="utf-8"))
    markdown = (run_dir / "artifacts" / "page.md").read_text(encoding="utf-8")
    validation = json.loads((run_dir / "validation" / "validation-report.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    expected_title = str(case["expected_title"])
    actual_title = metadata["document"]["title"]["value"]
    if actual_title != expected_title:
        errors.append(f"{case['name']}: title mismatch: {actual_title!r}")

    if validation["status"] != "pass":
        errors.append(f"{case['name']}: validation failed: {validation['errors']}")

    if not manifest["validation"]["schema_valid"]:
        errors.append(f"{case['name']}: manifest schema_valid is false")

    for warning in case.get("required_warnings", []):
        if warning not in metadata["extraction"]["warnings"]:
            errors.append(f"{case['name']}: missing warning {warning}")

    lower_markdown = markdown.lower()
    for term in case.get("forbidden_terms", []):
        if str(term).lower() in lower_markdown:
            errors.append(f"{case['name']}: forbidden term leaked: {term}")

    for term in case.get("required_terms", []):
        if str(term).lower() not in lower_markdown:
            errors.append(f"{case['name']}: required term missing: {term}")

    return errors


def run_safety_negative_cases() -> list[str]:
    errors: list[str] = []
    fake_root = OUTPUT_ROOT / "_inputs" / "fake-screenshot"
    fake_root.mkdir(parents=True, exist_ok=True)
    input_doc = json.loads((FIXTURE_ROOT / "x-thread.json").read_text(encoding="utf-8"))
    input_doc["assets"]["screenshots"][0]["path"] = "fake.png"
    (fake_root / "fake.png").write_text("not an image\n", encoding="utf-8")
    fake_input = fake_root / "input.json"
    fake_input.write_text(json.dumps(input_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run_id = "eval-fake-screenshot-rejected"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "page_to_md_runner.py"),
            "--input",
            str(fake_input),
            "--url",
            "https://x.example.test/thread/fake",
            "--output-root",
            str(OUTPUT_ROOT),
            "--run-id",
            run_id,
            "--page-type",
            "x_thread",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    run_dir = OUTPUT_ROOT / run_id
    if completed.returncode != 0:
        errors.append(f"fake-screenshot-rejected: runner failed unexpectedly: {completed.stderr.strip()}")
    else:
        validation = json.loads((run_dir / "validation" / "validation-report.json").read_text(encoding="utf-8"))
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        if validation.get("status") != "fail" or manifest.get("run_status") != "failed":
            errors.append("fake-screenshot-rejected: disguised PNG did not fail closed")
        if any(item.get("type") == "screenshot" for item in manifest.get("evidence", [])):
            errors.append("fake-screenshot-rejected: invalid screenshot was registered as evidence")

    invalid_root = OUTPUT_ROOT / "_inputs" / "invalid-json"
    invalid_root.mkdir(parents=True, exist_ok=True)
    invalid_input = invalid_root / "input.json"
    invalid_input.write_text("{invalid\n", encoding="utf-8")
    retry_run_id = "eval-invalid-json-retry"
    invalid_command = [
        sys.executable,
        str(ROOT / "scripts" / "page_to_md_runner.py"),
        "--input",
        str(invalid_input),
        "--output-root",
        str(OUTPUT_ROOT),
        "--run-id",
        retry_run_id,
    ]
    invalid_result = subprocess.run(invalid_command, cwd=ROOT, text=True, capture_output=True)
    if invalid_result.returncode == 0 or (OUTPUT_ROOT / retry_run_id).exists():
        errors.append("invalid-json-retry: invalid JSON left an orphan run")
    retry_result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "page_to_md_runner.py"),
            "--input",
            str(FIXTURE_ROOT / "public-article.html"),
            "--output-root",
            str(OUTPUT_ROOT),
            "--run-id",
            retry_run_id,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if retry_result.returncode != 0 or not (OUTPUT_ROOT / retry_run_id / "manifest.json").is_file():
        errors.append("invalid-json-retry: same run_id could not be retried")

    malformed_root = OUTPUT_ROOT / "_inputs" / "malformed-capture"
    malformed_root.mkdir(parents=True, exist_ok=True)
    malformed_cases = {
        "document": ("document", []),
        "document-ast": ("document_ast", []),
        "warnings": ("warnings", 1),
    }
    for name, (field, malformed_value) in malformed_cases.items():
        malformed_doc = json.loads((FIXTURE_ROOT / "x-thread.json").read_text(encoding="utf-8"))
        malformed_doc[field] = malformed_value
        malformed_input = malformed_root / f"{name}.json"
        malformed_input.write_text(
            json.dumps(malformed_doc, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        malformed_run_id = f"eval-malformed-capture-{name}-retry"
        malformed_result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "page_to_md_runner.py"),
                "--input",
                str(malformed_input),
                "--output-root",
                str(OUTPUT_ROOT),
                "--run-id",
                malformed_run_id,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if malformed_result.returncode == 0 or (OUTPUT_ROOT / malformed_run_id).exists():
            errors.append(f"malformed-capture-{name}: malformed capture left an orphan run")
        malformed_retry = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "page_to_md_runner.py"),
                "--input",
                str(FIXTURE_ROOT / "public-article.html"),
                "--output-root",
                str(OUTPUT_ROOT),
                "--run-id",
                malformed_run_id,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if malformed_retry.returncode != 0 or not (OUTPUT_ROOT / malformed_run_id / "manifest.json").is_file():
            errors.append(f"malformed-capture-{name}: same run_id could not be retried")
    return errors


def main() -> int:
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    all_errors: list[str] = []
    for case in load_cases():
        all_errors.extend(run_case(case))
    all_errors.extend(run_safety_negative_cases())

    if all_errors:
        print("FAIL")
        for error in all_errors:
            print(f"- {error}")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
