from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "evals" / ".tmp" / "distribution"


def main() -> int:
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "plugin_package.py"),
        "--output-dir",
        str(OUTPUT_ROOT),
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    errors: list[str] = []
    if completed.returncode != 0:
        errors.append(f"package command failed: {completed.stderr.strip()} {completed.stdout.strip()}".strip())
    manifest = json.loads((OUTPUT_ROOT / "package-manifest.json").read_text(encoding="utf-8"))
    package_path = OUTPUT_ROOT / manifest["package"]
    if not package_path.exists():
        errors.append("package zip missing")
    else:
        with zipfile.ZipFile(package_path, "r") as archive:
            names = set(archive.namelist())
        if ".codex-plugin/plugin.json" not in names:
            errors.append("plugin manifest missing from package")
        if any(name.startswith("evals/.tmp/") or name.startswith(".git/") for name in names):
            errors.append("package includes excluded runtime or git paths")
    if manifest["validation"]["status"] != "pass":
        errors.append(f"package validation failed: {manifest['validation']['errors']}")
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
