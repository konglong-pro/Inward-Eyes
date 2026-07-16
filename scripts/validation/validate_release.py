from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_ROOT = Path(__file__).resolve().parent
for path in (SCRIPT_ROOT, VALIDATION_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from inward_eyes.distribution import validate_distribution_inputs
from validate_contract_drift import validate_contract_drift
from validate_json_schema import resolve_pointer


def _iter_local_refs(value: Any, label: str = "$") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            nested_label = f"{label}.{key}"
            if key == "$ref" and isinstance(nested, str):
                found.append((nested_label, nested))
            found.extend(_iter_local_refs(nested, nested_label))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            found.extend(_iter_local_refs(nested, f"{label}[{index}]"))
    return found


def validate_schema_set(root: Path) -> list[str]:
    errors: list[str] = []
    schema_dir = root / "schemas"
    if not schema_dir.is_dir():
        return ["RELEASE_SCHEMAS_DIRECTORY_MISSING"]
    schema_paths = sorted(schema_dir.glob("*.schema.json"))
    if not schema_paths:
        return ["RELEASE_SCHEMAS_EMPTY"]
    for path in schema_paths:
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"RELEASE_SCHEMA_INVALID:{path.name}:{exc.__class__.__name__}:{exc}")
            continue
        if not isinstance(schema, dict):
            errors.append(f"RELEASE_SCHEMA_NOT_OBJECT:{path.name}")
            continue
        for label, reference in _iter_local_refs(schema):
            if not reference.startswith("#"):
                errors.append(f"RELEASE_SCHEMA_EXTERNAL_REF:{path.name}:{label}:{reference}")
                continue
            pointer = reference[1:]
            try:
                resolve_pointer(schema, pointer)
            except (IndexError, KeyError, TypeError, ValueError) as exc:
                errors.append(f"RELEASE_SCHEMA_REF_UNRESOLVED:{path.name}:{label}:{reference}:{exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate portable release inputs without creating a package.")
    parser.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parents[2]))
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = validate_distribution_inputs(root)
    errors = list(report["errors"])
    try:
        errors.extend(validate_contract_drift(root))
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError, SyntaxError) as exc:
        errors.append(f"RELEASE_CONTRACT_DRIFT_CHECK_FAILED:{exc.__class__.__name__}:{exc}")
    errors.extend(validate_schema_set(root))
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
