from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "evals" / ".tmp" / "distribution"
SCRIPT_ROOT = ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import inward_eyes.distribution as distribution
from inward_eyes.distribution import (
    PACKAGE_INVENTORY,
    REQUIRED_PACKAGE_PATHS,
    build_distribution_package,
    load_package_inventory,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_package(root: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "plugin_package.py"),
            "--root",
            str(root),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def _create_invalid_fixture(root: Path, capabilities: list[str]) -> None:
    manifest = {
        "name": "fixture-plugin",
        "version": "1.0.0",
        "description": "Distribution failure fixture.",
        "author": {"name": "Fixture"},
        "license": "MIT",
        "skills": "./skills/",
        "interface": {
            "displayName": "Fixture",
            "shortDescription": "Fixture plugin.",
            "longDescription": "Fixture plugin for deterministic package failure tests.",
            "developerName": "Fixture",
            "category": "Productivity",
            "capabilities": capabilities,
            "defaultPrompt": ["Validate the fixture."],
        },
    }
    manifest_path = root / ".codex-plugin" / "plugin.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for relative_path in sorted(REQUIRED_PACKAGE_PATHS - {PACKAGE_INVENTORY, ".codex-plugin/plugin.json", "LICENSE"}):
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")
    (root / "LICENSE").write_text(
        "MIT License\n\nPermission is hereby granted, free of charge, to any person obtaining a copy.\n",
        encoding="utf-8",
    )
    inventory = sorted(REQUIRED_PACKAGE_PATHS)
    (root / PACKAGE_INVENTORY).write_text("\n".join(inventory) + "\n", encoding="utf-8")


def main() -> int:
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    package_root = OUTPUT_ROOT / "package-root"
    package_files, inventory_errors = load_package_inventory(ROOT)
    if inventory_errors:
        print("FAIL")
        for error in inventory_errors:
            print(f"- source inventory invalid: {error}")
        return 1
    for source in package_files:
        destination = package_root / source.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)

    sentinel = package_root / "scripts" / "untracked-package-sentinel.txt"
    sensitive_sentinel = package_root / "scripts" / "untracked-secret.key"
    first_output = OUTPUT_ROOT / "first"
    second_output = OUTPUT_ROOT / "second"

    sentinel.write_text("must not be packaged\n", encoding="utf-8")
    sensitive_sentinel.write_text("must not be packaged\n", encoding="utf-8")
    completed = _run_package(package_root, first_output)
    repeated = _run_package(package_root, second_output)

    for label, result in (("first", completed), ("second", repeated)):
        if result.returncode != 0:
            errors.append(f"{label} package command failed: {result.stderr.strip()} {result.stdout.strip()}".strip())

    first_manifest_path = first_output / "package-manifest.json"
    second_manifest_path = second_output / "package-manifest.json"
    if not first_manifest_path.is_file() or not second_manifest_path.is_file():
        errors.append("package manifest missing")
    else:
        first_manifest = json.loads(first_manifest_path.read_text(encoding="utf-8"))
        second_manifest = json.loads(second_manifest_path.read_text(encoding="utf-8"))
        if first_manifest["validation"]["status"] != "pass":
            errors.append(f"package validation failed: {first_manifest['validation']['errors']}")
        package_name = first_manifest.get("package")
        first_package = first_output / package_name if isinstance(package_name, str) else None
        second_package = second_output / str(second_manifest.get("package"))
        if first_package is None or not first_package.is_file() or not second_package.is_file():
            errors.append("package zip missing")
        else:
            if first_package.read_bytes() != second_package.read_bytes():
                errors.append("package archive is not reproducible")
            archive_sha256 = _sha256(first_package)
            if first_manifest.get("archive_sha256") != archive_sha256:
                errors.append("package manifest archive hash mismatch")
            if second_manifest.get("archive_sha256") != archive_sha256:
                errors.append("repeated package archive hash mismatch")
            with zipfile.ZipFile(first_package, "r") as archive:
                infos = archive.infolist()
                names = [info.filename for info in infos]
                name_set = set(names)
                for info in infos:
                    if info.date_time != (1980, 1, 1, 0, 0, 0):
                        errors.append(f"non-deterministic zip timestamp: {info.filename}")
                        break
            if names != sorted(names):
                errors.append("package entries are not sorted")
            required_names = {
                ".codex-plugin/plugin.json",
                "AGENTS.md",
                "LICENSE",
                PACKAGE_INVENTORY,
                "evals/run_eval.py",
                "examples/browser-research-input.json",
                "scripts/validation/validate_plugin.py",
                "scripts/validation/validate_release.py",
            }
            missing = required_names - name_set
            if missing:
                errors.append(f"package missing required content: {sorted(missing)}")
            forbidden = [
                name
                for name in names
                if name.startswith((".git/", ".github/", "browser-operator-runs/", "dist/", "evals/.tmp/"))
                or "/__pycache__/" in f"/{name}"
                or name.endswith(".pyc")
            ]
            if forbidden:
                errors.append(f"package includes excluded paths: {forbidden}")
            for unexpected in ("scripts/untracked-package-sentinel.txt", "scripts/untracked-secret.key"):
                if unexpected in name_set:
                    errors.append(f"package includes unlisted file: {unexpected}")
            file_records = {record["path"]: record for record in first_manifest.get("files", [])}
            if set(file_records) != name_set:
                errors.append("package manifest file inventory differs from archive")
            else:
                for record_path, record in file_records.items():
                    file_path = package_root / record_path
                    if record.get("bytes") != file_path.stat().st_size or record.get("sha256") != _sha256(file_path):
                        errors.append(f"package file record mismatch: {record_path}")
                        break

    invalid_root = OUTPUT_ROOT / "invalid-fixture"
    _create_invalid_fixture(invalid_root, ["Read", "Write"])
    invalid_output = OUTPUT_ROOT / "invalid-output"
    invalid_output.mkdir(parents=True, exist_ok=True)
    stale_invalid_package = invalid_output / "fixture-plugin-1.0.0.zip"
    stale_invalid_package.write_bytes(b"stale package")
    invalid_manifest = build_distribution_package(invalid_root, invalid_output)
    if "PLUGIN_CAPABILITIES_NOT_READ_ONLY" not in invalid_manifest["validation"]["errors"]:
        errors.append("capability mismatch did not fail validation")
    if invalid_manifest.get("package") is not None or list(invalid_output.glob("*.zip")):
        errors.append("capability mismatch created a zip before validation passed")

    invalid_identity_root = OUTPUT_ROOT / "invalid-identity-fixture"
    _create_invalid_fixture(invalid_identity_root, ["Read"])
    invalid_identity_manifest_path = invalid_identity_root / ".codex-plugin" / "plugin.json"
    invalid_identity_manifest = json.loads(invalid_identity_manifest_path.read_text(encoding="utf-8"))
    invalid_identity_manifest["version"] = "invalid/version"
    invalid_identity_manifest_path.write_text(
        json.dumps(invalid_identity_manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    invalid_identity_output = OUTPUT_ROOT / "invalid-identity-output"
    invalid_identity_output.mkdir(parents=True, exist_ok=True)
    prior_package_name = "fixture-plugin-1.0.0.zip"
    (invalid_identity_output / prior_package_name).write_bytes(b"stale package")
    (invalid_identity_output / "package-manifest.json").write_text(
        json.dumps({"package": prior_package_name}, indent=2) + "\n",
        encoding="utf-8",
    )
    invalid_identity_result = build_distribution_package(invalid_identity_root, invalid_identity_output)
    if "PLUGIN_VERSION_INVALID" not in invalid_identity_result["validation"]["errors"]:
        errors.append("invalid plugin identity did not fail validation")
    if list(invalid_identity_output.glob("*.zip")):
        errors.append("invalid plugin identity left the previously recorded stale zip")

    escaped_manifest_output = OUTPUT_ROOT / "escaped-recorded-package-output"
    escaped_manifest_output.mkdir(parents=True, exist_ok=True)
    outside_package = OUTPUT_ROOT / "outside-recorded-package.zip"
    outside_package.write_bytes(b"must remain")
    (escaped_manifest_output / "package-manifest.json").write_text(
        json.dumps({"package": "..\\outside-recorded-package.zip"}, indent=2) + "\n",
        encoding="utf-8",
    )
    build_distribution_package(invalid_identity_root, escaped_manifest_output)
    if not outside_package.is_file():
        errors.append("recorded package path traversal removed a file outside the output directory")

    sensitive_cases = {
        "private-key": "scripts/secret.key",
        "token": "scripts/token.json",
        "token-text": "scripts/token.txt",
        "tokens": "scripts/tokens.json",
        "auth": "scripts/auth.json",
        "auth-database": "scripts/auth.db",
        "api-token": "scripts/api_token.yaml",
        "api-key": "scripts/api_key.json",
        "api-key-hyphen": "scripts/service-api-key.yaml",
        "private-key-yaml": "scripts/private_key.yaml",
        "client-secret": "scripts/client_secret.json",
        "client-secret-export": "scripts/client_secret_123.apps.example.test.json",
        "secret-backup": "scripts/service_secret_backup.json",
        "password": "scripts/password.txt",
        "passwords": "scripts/passwords.json",
        "passwords-csv": "scripts/passwords.csv",
        "passwd": "scripts/service-passwd.ini",
        "storage-state": "scripts/storage_state.json",
        "npmrc": "scripts/.npmrc",
        "browser-cookies": "profiles/chrome-profile/Cookies",
        "browser-login-data": "profiles/chrome-profile/Login Data",
    }
    for label, relative_path in sensitive_cases.items():
        sensitive_root = OUTPUT_ROOT / f"sensitive-{label}-fixture"
        _create_invalid_fixture(sensitive_root, ["Read"])
        sensitive_path = sensitive_root / Path(*relative_path.split("/"))
        sensitive_path.parent.mkdir(parents=True, exist_ok=True)
        sensitive_path.write_text("fixture secret\n", encoding="utf-8")
        inventory_path = sensitive_root / PACKAGE_INVENTORY
        inventory_path.write_text(
            inventory_path.read_text(encoding="utf-8") + f"{relative_path}\n",
            encoding="utf-8",
        )
        sensitive_output = OUTPUT_ROOT / f"sensitive-{label}-output"
        sensitive_manifest = build_distribution_package(sensitive_root, sensitive_output)
        if not any(
            error.startswith("PACKAGE_PATH_SENSITIVE:") for error in sensitive_manifest["validation"]["errors"]
        ):
            errors.append(f"sensitive inventory entry did not fail validation: {relative_path}")
        if sensitive_manifest.get("package") is not None or list(sensitive_output.glob("*.zip")):
            errors.append(f"sensitive inventory entry created a zip before validation passed: {relative_path}")

    for safe_path in (
        "profiles/site_profiles.json",
        "docs/authentication.md",
        "docs/tokenization.md",
        "docs/session-management.md",
        "scripts/tokenizer.py",
        "scripts/password_policy.py",
    ):
        if distribution._sensitive_reason(safe_path) is not None:
            errors.append(f"normal package path was misclassified as sensitive: {safe_path}")

    unsafe_inventory_paths = {
        "scripts/example.py:secret": "PACKAGE_PATH_WINDOWS_UNSAFE:",
        "scripts/bad./file.txt": "PACKAGE_PATH_WINDOWS_UNSAFE:",
        "scripts/bad /file.txt": "PACKAGE_PATH_WINDOWS_UNSAFE:",
        "scripts/CON": "PACKAGE_PATH_WINDOWS_UNSAFE:",
        "scripts/com1.txt": "PACKAGE_PATH_WINDOWS_UNSAFE:",
        "scripts/trailing ": "PACKAGE_PATH_NOT_NORMALIZED:",
    }
    for index, (relative_path, expected_error) in enumerate(unsafe_inventory_paths.items(), 1):
        unsafe_root = OUTPUT_ROOT / f"unsafe-path-{index}-fixture"
        _create_invalid_fixture(unsafe_root, ["Read"])
        inventory_path = unsafe_root / PACKAGE_INVENTORY
        inventory_path.write_text(
            inventory_path.read_text(encoding="utf-8") + f"{relative_path}\n",
            encoding="utf-8",
        )
        _, unsafe_errors = load_package_inventory(unsafe_root)
        if not any(error.startswith(expected_error) for error in unsafe_errors):
            errors.append(f"unsafe inventory path was accepted: {relative_path}")

    atomic_output = OUTPUT_ROOT / "atomic-write-failure"
    atomic_output.mkdir(parents=True, exist_ok=True)
    atomic_target = atomic_output / "atomic-test.zip"
    try:
        distribution._write_reproducible_zip(
            ROOT,
            atomic_target,
            [ROOT / "LICENSE", OUTPUT_ROOT / "missing-package-source.txt"],
        )
    except OSError:
        pass
    else:
        errors.append("synthetic package read failure unexpectedly succeeded")
    if atomic_target.exists() or any(path.suffix == ".tmp" for path in atomic_output.iterdir()):
        errors.append("synthetic package read failure left a partial archive")

    interrupted_output = OUTPUT_ROOT / "interrupted-build"
    interrupted_output.mkdir(parents=True, exist_ok=True)
    current_manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    interrupted_target = interrupted_output / f"{current_manifest['name']}-{current_manifest['version']}.zip"
    interrupted_target.write_bytes(b"stale package")
    try:
        with patch.object(distribution, "_write_reproducible_zip", side_effect=OSError("synthetic write failure")):
            build_distribution_package(ROOT, interrupted_output)
    except OSError:
        pass
    else:
        errors.append("synthetic package write failure unexpectedly succeeded")
    if interrupted_target.exists() or list(interrupted_output.glob("*.zip")):
        errors.append("synthetic package write failure left a stale or partial archive")

    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
