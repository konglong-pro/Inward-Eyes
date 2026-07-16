from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from inward_eyes.io import write_json


PACKAGE_INVENTORY = "package-files.txt"
ALLOWED_TOP_LEVEL = {
    ".codex-plugin",
    "AGENTS.md",
    "CONTEXT.md",
    "LICENSE",
    "README.md",
    "docs",
    "evals",
    "examples",
    PACKAGE_INVENTORY,
    "profiles",
    "schemas",
    "scripts",
    "skills",
}
REQUIRED_PACKAGE_PATHS = {
    ".codex-plugin/plugin.json",
    "AGENTS.md",
    "LICENSE",
    PACKAGE_INVENTORY,
    "schemas/document_ast.schema.json",
    "schemas/run_manifest.schema.json",
    "schemas/source_record.schema.json",
    "schemas/validation_report.schema.json",
    "scripts/plugin_package.py",
    "scripts/validation/validate_contract_drift.py",
    "scripts/validation/validate_plugin.py",
    "scripts/validation/validate_release.py",
    "skills/browser-research/SKILL.md",
    "skills/page-to-md/SKILL.md",
    "skills/price-compare/SKILL.md",
}
FORBIDDEN_PATH_PARTS = {
    ".git",
    ".github",
    ".pytest_cache",
    "__pycache__",
    "browser-operator-runs",
    "dist",
}
SENSITIVE_NAMES = {
    ".env",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "auth.json",
    "cookies",
    "cookies.json",
    "credentials.json",
    "id_dsa",
    "id_ed25519",
    "id_rsa",
    "local_storage.json",
    "login data",
    "session_storage.json",
    "secrets.json",
    "storage-state.json",
    "storage_state.json",
    "token.json",
    "tokens.json",
}
SENSITIVE_SUFFIXES = {".key", ".p12", ".pem", ".pfx"}
SENSITIVE_DATA_STEMS = {
    "api-key",
    "api_key",
    "apikey",
    "auth",
    "client-secret",
    "client_secret",
    "clientsecret",
    "cookie",
    "cookies",
    "credential",
    "credentials",
    "key",
    "keys",
    "passphrase",
    "passwd",
    "password",
    "passwords",
    "private-key",
    "private_key",
    "privatekey",
    "secret",
    "secret-key",
    "secret_key",
    "secretkey",
    "secrets",
    "session",
    "sessions",
    "storage-state",
    "storage_state",
    "token",
    "tokens",
}
SENSITIVE_DATA_SUFFIXES = {
    "",
    ".cfg",
    ".conf",
    ".csv",
    ".db",
    ".env",
    ".ini",
    ".json",
    ".properties",
    ".sqlite",
    ".sqlite3",
    ".toml",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
SENSITIVE_STEM_SUFFIXES = (
    "-api-key",
    "_api_key",
    "-auth",
    "_auth",
    "-client-secret",
    "_client_secret",
    "-cookie",
    "_cookie",
    "-cookies",
    "_cookies",
    "-credential",
    "_credential",
    "-credentials",
    "_credentials",
    "-passphrase",
    "_passphrase",
    "-passwd",
    "_passwd",
    "-password",
    "_password",
    "-private-key",
    "_private_key",
    "-secret",
    "_secret",
    "-secret-key",
    "_secret_key",
    "-secrets",
    "_secrets",
    "-session",
    "_session",
    "-storage-state",
    "_storage_state",
    "-token",
    "_token",
    "-tokens",
    "_tokens",
)
SENSITIVE_STEM_TOKENS = {
    "apikey",
    "auth",
    "clientsecret",
    "cookie",
    "cookies",
    "credential",
    "credentials",
    "passphrase",
    "passwd",
    "password",
    "passwords",
    "privatekey",
    "secret",
    "secretkey",
    "secrets",
    "session",
    "sessions",
    "token",
    "tokens",
}
SENSITIVE_STEM_TOKEN_PAIRS = {
    ("api", "key"),
    ("api", "keys"),
    ("client", "secret"),
    ("private", "key"),
    ("secret", "key"),
}
SENSITIVE_PATH_PARTS = {
    "browser-profile",
    "browser profile",
    "browser_profile",
    "chrome user data",
    "chrome-profile",
    "chrome_profile",
    "firefox-profile",
    "firefox_profile",
    "user data",
    "user-data",
    "user-data-dir",
    "user_data_dir",
}
WINDOWS_RESERVED_NAMES = {
    "aux",
    "clock$",
    "con",
    "conin$",
    "conout$",
    "nul",
    "prn",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}
WINDOWS_FORBIDDEN_CHARACTERS = set('<>:"|?*')
PLUGIN_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def _status_report(errors: list[str], warnings: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
        "requires_manual_review": bool(errors or warnings),
        "run_status": "failed" if errors else "partial" if warnings else "complete",
        "validation_status": "failed" if errors else "passed",
        "manual_review": {
            "required": bool(errors or warnings),
            "severity": "blocking" if errors else "warning" if warnings else "info",
            "reasons": [
                {
                    "code": code.split(":", 1)[0],
                    "message": code.replace("_", " ").replace(":", ": "),
                    "severity": "blocking" if code in errors else "warning",
                    "artifact": ".codex-plugin/plugin.json" if "PLUGIN" in code else PACKAGE_INVENTORY,
                }
                for code in errors + warnings
            ],
        },
        "completion_blockers": errors,
    }


def _load_plugin_manifest(root: Path) -> dict[str, Any]:
    manifest_path = root / ".codex-plugin" / "plugin.json"
    loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("plugin manifest must be a JSON object")
    return loaded


def _manifest_path(root: Path, value: str) -> Path | None:
    candidate = Path(value)
    if candidate.is_absolute():
        return None
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


def validate_plugin_manifest(root: Path) -> dict[str, Any]:
    root = root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    manifest_path = root / ".codex-plugin" / "plugin.json"
    manifest: dict[str, Any] = {}
    if not manifest_path.is_file():
        errors.append("PLUGIN_MANIFEST_MISSING:.codex-plugin/plugin.json")
    elif manifest_path.is_symlink():
        errors.append("PLUGIN_MANIFEST_SYMLINK:.codex-plugin/plugin.json")
    else:
        try:
            manifest = _load_plugin_manifest(root)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"PLUGIN_MANIFEST_INVALID:{exc.__class__.__name__}:{exc}")

    name = manifest.get("name")
    if not isinstance(name, str) or not PLUGIN_NAME_PATTERN.fullmatch(name):
        errors.append("PLUGIN_NAME_INVALID")
    version = manifest.get("version")
    if not isinstance(version, str) or not SEMVER_PATTERN.fullmatch(version):
        errors.append("PLUGIN_VERSION_INVALID")
    for field in ("description", "license"):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            errors.append(f"PLUGIN_{field.upper()}_MISSING")
    if manifest.get("license") != "MIT":
        errors.append("PLUGIN_LICENSE_NOT_MIT")
    author = manifest.get("author")
    if not isinstance(author, dict) or not isinstance(author.get("name"), str) or not author["name"].strip():
        errors.append("PLUGIN_AUTHOR_NAME_MISSING")

    skills_value = manifest.get("skills")
    if not isinstance(skills_value, str) or not skills_value.strip():
        errors.append("PLUGIN_SKILLS_PATH_MISSING")
    else:
        skills_path = _manifest_path(root, skills_value)
        if skills_path is None:
            errors.append("PLUGIN_SKILLS_PATH_OUTSIDE_ROOT")
        elif not skills_path.is_dir():
            errors.append("PLUGIN_SKILLS_PATH_NOT_DIRECTORY")

    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        errors.append("PLUGIN_INTERFACE_MISSING")
        interface = {}
    for field in ("displayName", "shortDescription", "longDescription", "developerName", "category"):
        if not isinstance(interface.get(field), str) or not interface[field].strip():
            errors.append(f"PLUGIN_INTERFACE_{field.upper()}_MISSING")
    prompts = interface.get("defaultPrompt")
    if not isinstance(prompts, list) or not prompts or any(not isinstance(item, str) or not item.strip() for item in prompts):
        errors.append("PLUGIN_INTERFACE_DEFAULT_PROMPT_INVALID")
    if interface.get("capabilities") != ["Read"]:
        errors.append("PLUGIN_CAPABILITIES_NOT_READ_ONLY")

    report = _status_report(errors, warnings)
    report["manifest"] = manifest
    return report


def _sensitive_reason(relative_path: str) -> str | None:
    path = PurePosixPath(relative_path)
    if relative_path == "evals/.tmp" or relative_path.startswith("evals/.tmp/"):
        return "temporary eval output"
    lowered_parts = [part.lower() for part in path.parts]
    if any(part in FORBIDDEN_PATH_PARTS for part in lowered_parts):
        return "forbidden output or repository path"
    if any(part in SENSITIVE_PATH_PARTS for part in lowered_parts):
        return "browser profile path"
    name = path.name.lower()
    if name in SENSITIVE_NAMES or name.startswith(".env."):
        return "sensitive filename"
    suffix = path.suffix.lower()
    stem = name[: -len(suffix)] if suffix else name
    stem_tokens = tuple(token for token in re.split(r"[._-]+", stem) if token)
    token_pairs = set(zip(stem_tokens, stem_tokens[1:]))
    if suffix in SENSITIVE_DATA_SUFFIXES and (
        stem in SENSITIVE_DATA_STEMS
        or stem.endswith(SENSITIVE_STEM_SUFFIXES)
        or any(token in SENSITIVE_STEM_TOKENS for token in stem_tokens)
        or bool(token_pairs.intersection(SENSITIVE_STEM_TOKEN_PAIRS))
    ):
        return "sensitive data filename"
    if any(name.endswith(suffix) for suffix in SENSITIVE_SUFFIXES):
        return "sensitive file suffix"
    return None


def _windows_unsafe_component(component: str) -> str | None:
    if component.endswith((" ", ".")):
        return "component has a trailing space or dot"
    if any(character in WINDOWS_FORBIDDEN_CHARACTERS or ord(character) < 32 for character in component):
        return "component contains a Windows-forbidden character"
    base_name = component.split(".", 1)[0].casefold()
    if base_name in WINDOWS_RESERVED_NAMES:
        return "component uses a Windows device name"
    return None


def load_package_inventory(root: Path) -> tuple[list[Path], list[str]]:
    root = root.resolve()
    inventory_path = root / PACKAGE_INVENTORY
    errors: list[str] = []
    files: list[Path] = []
    if not inventory_path.is_file():
        return [], [f"PACKAGE_INVENTORY_MISSING:{PACKAGE_INVENTORY}"]
    if inventory_path.is_symlink():
        return [], [f"PACKAGE_INVENTORY_SYMLINK:{PACKAGE_INVENTORY}"]
    try:
        lines = inventory_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return [], [f"PACKAGE_INVENTORY_UNREADABLE:{exc.__class__.__name__}:{exc}"]

    seen: set[str] = set()
    seen_casefold: set[str] = set()
    for line_number, raw_line in enumerate(lines, 1):
        trimmed = raw_line.strip()
        if not trimmed or trimmed.startswith("#"):
            continue
        if raw_line != trimmed:
            errors.append(f"PACKAGE_PATH_NOT_NORMALIZED:{line_number}:{raw_line}")
            continue
        value = raw_line
        if "\\" in value:
            errors.append(f"PACKAGE_PATH_NOT_POSIX:{line_number}:{value}")
            continue
        pure_path = PurePosixPath(value)
        if pure_path.is_absolute() or not pure_path.parts or any(part in {"", ".", ".."} for part in pure_path.parts):
            errors.append(f"PACKAGE_PATH_INVALID:{line_number}:{value}")
            continue
        unsafe_component = next(
            (
                (part, reason)
                for part in pure_path.parts
                if (reason := _windows_unsafe_component(part)) is not None
            ),
            None,
        )
        if unsafe_component is not None:
            part, reason = unsafe_component
            errors.append(f"PACKAGE_PATH_WINDOWS_UNSAFE:{line_number}:{value}:{part}:{reason}")
            continue
        normalized = pure_path.as_posix()
        if normalized != value:
            errors.append(f"PACKAGE_PATH_NOT_NORMALIZED:{line_number}:{value}")
            continue
        folded = normalized.casefold()
        if normalized in seen or folded in seen_casefold:
            errors.append(f"PACKAGE_PATH_DUPLICATE:{line_number}:{normalized}")
            continue
        seen.add(normalized)
        seen_casefold.add(folded)
        if pure_path.parts[0] not in ALLOWED_TOP_LEVEL:
            errors.append(f"PACKAGE_PATH_TOP_LEVEL_NOT_ALLOWED:{line_number}:{normalized}")
            continue
        sensitive_reason = _sensitive_reason(normalized)
        if sensitive_reason:
            errors.append(f"PACKAGE_PATH_SENSITIVE:{line_number}:{normalized}:{sensitive_reason}")
            continue
        candidate = root / Path(*pure_path.parts)
        cursor = root
        has_symlink = False
        for part in pure_path.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                has_symlink = True
                break
        if has_symlink:
            errors.append(f"PACKAGE_PATH_SYMLINK:{line_number}:{normalized}")
            continue
        path = candidate.resolve()
        try:
            path.relative_to(root)
        except ValueError:
            errors.append(f"PACKAGE_PATH_OUTSIDE_ROOT:{line_number}:{normalized}")
            continue
        if not path.exists():
            errors.append(f"PACKAGE_PATH_MISSING:{line_number}:{normalized}")
            continue
        if not path.is_file():
            errors.append(f"PACKAGE_PATH_NOT_FILE:{line_number}:{normalized}")
            continue
        files.append(path)

    listed = {path.relative_to(root).as_posix() for path in files}
    if PACKAGE_INVENTORY not in listed:
        errors.append(f"PACKAGE_INVENTORY_NOT_SELF_LISTED:{PACKAGE_INVENTORY}")
    for required in sorted(REQUIRED_PACKAGE_PATHS - listed):
        errors.append(f"PACKAGE_REQUIRED_PATH_NOT_LISTED:{required}")
    if not files:
        errors.append("PACKAGE_INVENTORY_EMPTY")
    return sorted(files, key=lambda path: path.relative_to(root).as_posix()), errors


def validate_distribution_inputs(root: Path) -> dict[str, Any]:
    root = root.resolve()
    plugin_report = validate_plugin_manifest(root)
    files, inventory_errors = load_package_inventory(root)
    errors = list(plugin_report["errors"]) + inventory_errors
    warnings = list(plugin_report["warnings"])
    license_path = root / "LICENSE"
    if license_path.is_file():
        try:
            license_text = license_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"DISTRIBUTION_LICENSE_UNREADABLE:{exc.__class__.__name__}:{exc}")
        else:
            if "MIT License" not in license_text or "Permission is hereby granted" not in license_text:
                errors.append("DISTRIBUTION_LICENSE_CONTENT_INVALID")
    else:
        errors.append("DISTRIBUTION_LICENSE_MISSING")

    report = _status_report(errors, warnings)
    report["inventory"] = {
        "path": PACKAGE_INVENTORY,
        "file_count": len(files),
        "files": [path.relative_to(root).as_posix() for path in files],
    }
    return report


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _remove_file_if_present(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if not path.is_file() and not path.is_symlink():
        raise IsADirectoryError(f"expected a file path, found a directory: {path}")
    path.unlink()


def _write_reproducible_zip(root: Path, package_path: Path, files: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    temporary_handle = tempfile.NamedTemporaryFile(
        mode="wb",
        prefix=f".{package_path.name}.",
        suffix=".tmp",
        dir=package_path.parent,
        delete=False,
    )
    temporary_path = Path(temporary_handle.name)
    temporary_handle.close()
    try:
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in files:
                relative_path = path.relative_to(root).as_posix()
                payload = path.read_bytes()
                records.append({"path": relative_path, "bytes": len(payload), "sha256": _sha256_bytes(payload)})
                info = zipfile.ZipInfo(relative_path, FIXED_ZIP_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, payload, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        with temporary_path.open("r+b") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary_path, package_path)
        return records
    finally:
        if temporary_path.exists() or temporary_path.is_symlink():
            temporary_path.unlink()


def _standard_package_name(manifest: dict[str, Any]) -> str | None:
    name = manifest.get("name")
    version = manifest.get("version")
    if not isinstance(name, str) or not PLUGIN_NAME_PATTERN.fullmatch(name):
        return None
    if not isinstance(version, str) or not SEMVER_PATTERN.fullmatch(version):
        return None
    return f"{name}-{version}.zip"


def _recorded_package_path(output_dir: Path, manifest_path: Path) -> Path | None:
    if not manifest_path.is_file() or manifest_path.is_symlink():
        return None
    try:
        loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    package_name = loaded.get("package") if isinstance(loaded, dict) else None
    if not isinstance(package_name, str):
        return None
    pure_path = PurePosixPath(package_name)
    if (
        pure_path.is_absolute()
        or "\\" in package_name
        or len(pure_path.parts) != 1
        or pure_path.suffix.lower() != ".zip"
        or _windows_unsafe_component(package_name) is not None
    ):
        return None
    return output_dir / package_name


def _append_report_error(report: dict[str, Any], error: str) -> None:
    errors = [str(item) for item in report.get("errors", [])]
    warnings = [str(item) for item in report.get("warnings", [])]
    errors.append(error)
    inventory = report.get("inventory")
    report.clear()
    report.update(_status_report(errors, warnings))
    if inventory is not None:
        report["inventory"] = inventory


def build_distribution_package(root: Path, output_dir: Path) -> dict[str, Any]:
    root = root.resolve()
    output_dir = output_dir.resolve()
    report = validate_distribution_inputs(root)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = validate_plugin_manifest(root).get("manifest", {})
    package_name = _standard_package_name(manifest)
    package_path = output_dir / package_name if package_name is not None else None
    manifest_path = output_dir / "package-manifest.json"
    recorded_package_path = _recorded_package_path(output_dir, manifest_path)
    stale_package_paths = {
        path
        for path in (package_path, recorded_package_path)
        if path is not None
    }
    for stale_package_path in stale_package_paths:
        try:
            _remove_file_if_present(stale_package_path)
        except OSError as exc:
            _append_report_error(
                report,
                f"DISTRIBUTION_STALE_PACKAGE_REMOVE_FAILED:{stale_package_path.name}:{exc.__class__.__name__}:{exc}",
            )
    _remove_file_if_present(manifest_path)
    package_manifest: dict[str, Any] = {
        "schema_version": "1.0",
        "package": None,
        "archive_sha256": None,
        "plugin_name": manifest.get("name"),
        "plugin_version": manifest.get("version"),
        "inventory": PACKAGE_INVENTORY,
        "file_count": 0,
        "files": [],
        "validation": report,
    }
    if report["status"] == "pass":
        files, inventory_errors = load_package_inventory(root)
        if inventory_errors:
            for error in inventory_errors:
                _append_report_error(report, f"PACKAGE_INVENTORY_CHANGED:{error}")
            package_manifest["validation"] = report
        else:
            if package_name is None or package_path is None:
                raise RuntimeError("validated plugin manifest did not produce a safe package name")
            try:
                records = _write_reproducible_zip(root, package_path, files)
                package_manifest.update(
                    {
                        "package": package_name,
                        "archive_sha256": _sha256_bytes(package_path.read_bytes()),
                        "file_count": len(records),
                        "files": records,
                    }
                )
            except BaseException:
                _remove_file_if_present(package_path)
                raise
    try:
        write_json(manifest_path, package_manifest)
    except BaseException:
        if package_path is not None:
            _remove_file_if_present(package_path)
        raise
    return package_manifest
