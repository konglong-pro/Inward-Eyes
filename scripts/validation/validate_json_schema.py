from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _type_ok(value: Any, expected: Any) -> bool:
    expected_types = expected if isinstance(expected, list) else [expected]
    for item in expected_types:
        if item == "null" and value is None:
            return True
        if item == "object" and isinstance(value, dict):
            return True
        if item == "array" and isinstance(value, list):
            return True
        if item == "string" and isinstance(value, str):
            return True
        if item == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if item == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
        if item == "boolean" and isinstance(value, bool):
            return True
    return False


def validate_minimal(schema: dict[str, Any], data: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type and not _type_ok(data, expected_type):
        errors.append(f"{path}: expected {expected_type}")
        return errors

    if "const" in schema and data != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}")

    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path}: expected one of {schema['enum']!r}")

    if isinstance(data, dict):
        for required_key in schema.get("required", []):
            if required_key not in data:
                errors.append(f"{path}.{required_key}: missing required key")
        properties = schema.get("properties", {})
        for key, subschema in properties.items():
            if key in data and "$ref" not in subschema:
                errors.extend(validate_minimal(subschema, data[key], f"{path}.{key}"))

    if isinstance(data, list) and "items" in schema:
        item_schema = schema["items"]
        if "$ref" not in item_schema:
            for index, item in enumerate(data):
                errors.extend(validate_minimal(item_schema, item, f"{path}[{index}]"))

    if isinstance(data, str) and "minLength" in schema and len(data) < int(schema["minLength"]):
        errors.append(f"{path}: shorter than minLength {schema['minLength']}")

    return errors


def resolve_pointer(data: Any, pointer: str) -> Any:
    if pointer in {"", "/"}:
        return data
    if not pointer.startswith("/"):
        raise ValueError("pointer must start with /")
    current = data
    for raw_part in pointer.lstrip("/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise ValueError(f"pointer segment not resolvable: {part}")
    return current


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal JSON schema validation for Inward Eyes artifacts.")
    parser.add_argument("--schema", required=True)
    parser.add_argument("--json", required=True)
    parser.add_argument("--pointer", help="Optional JSON Pointer selecting a nested value to validate.")
    args = parser.parse_args()

    schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))
    data = json.loads(Path(args.json).read_text(encoding="utf-8"))
    if args.pointer:
        try:
            data = resolve_pointer(data, args.pointer)
        except (KeyError, IndexError, ValueError) as exc:
            print(f"pointer resolution failed: {exc}")
            return 1
    errors = validate_minimal(schema, data)
    if errors:
        for error in errors:
            print(error)
        return 1
    print("schema validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
