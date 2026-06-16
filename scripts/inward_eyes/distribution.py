from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from inward_eyes.io import write_json


EXCLUDED_DIRS = {".git", "__pycache__", ".pytest_cache", "browser-operator-runs", "dist"}
EXCLUDED_PREFIXES = {"evals/.tmp/"}


def _load_plugin_manifest(root: Path) -> dict[str, Any]:
    manifest_path = root / ".codex-plugin" / "plugin.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _included_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            continue
        parts = set(path.relative_to(root).parts)
        if parts.intersection(EXCLUDED_DIRS):
            continue
        if any(rel.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
            continue
        if path.suffix == ".pyc":
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def validate_distribution_inputs(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    manifest_path = root / ".codex-plugin" / "plugin.json"
    if not manifest_path.exists():
        errors.append("DISTRIBUTION_PLUGIN_MANIFEST_MISSING")
        manifest = {}
    else:
        manifest = _load_plugin_manifest(root)
    for path in ("skills/page-to-md/SKILL.md", "skills/browser-research/SKILL.md", "skills/price-compare/SKILL.md"):
        if not (root / path).exists():
            errors.append(f"DISTRIBUTION_SKILL_MISSING:{path}")
    if not (root / "schemas").exists():
        errors.append("DISTRIBUTION_SCHEMAS_MISSING")
    if not (root / "scripts").exists():
        errors.append("DISTRIBUTION_SCRIPTS_MISSING")
    if manifest.get("interface", {}).get("capabilities") != ["Read"]:
        warnings.append("DISTRIBUTION_CAPABILITIES_NOT_READ_ONLY")
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
                    "code": code,
                    "message": code.replace("_", " ").replace(":", ": "),
                    "severity": "blocking" if code in errors else "warning",
                    "artifact": ".codex-plugin/plugin.json",
                }
                for code in errors + warnings
            ],
        },
        "completion_blockers": errors,
    }


def build_distribution_package(root: Path, output_dir: Path) -> dict[str, Any]:
    report = validate_distribution_inputs(root)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = _load_plugin_manifest(root) if not report["errors"] else {"name": "inward-eyes", "version": "unknown"}
    package_name = f"{manifest.get('name', 'inward-eyes')}-{manifest.get('version', 'unknown')}.zip"
    package_path = output_dir / package_name
    files = _included_files(root)
    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(root).as_posix())
    package_manifest = {
        "schema_version": "1.0",
        "package": package_path.name,
        "plugin_name": manifest.get("name"),
        "plugin_version": manifest.get("version"),
        "file_count": len(files),
        "excluded_dirs": sorted(EXCLUDED_DIRS),
        "excluded_prefixes": sorted(EXCLUDED_PREFIXES),
        "validation": report,
    }
    write_json(output_dir / "package-manifest.json", package_manifest)
    return package_manifest
