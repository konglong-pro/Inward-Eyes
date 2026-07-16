from __future__ import annotations

import argparse
import json
import math
import re
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


def resolve_pointer(data: Any, pointer: str) -> Any:
    if pointer == "":
        return data
    if not pointer.startswith("/"):
        raise ValueError("pointer must start with /")
    current = data
    for raw_part in pointer[1:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise ValueError(f"pointer segment not resolvable: {part}")
    return current


def _resolve_local_ref(root_schema: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#"):
        raise ValueError(f"external $ref is not supported: {ref}")
    pointer = ref[1:]
    resolved = root_schema if not pointer else resolve_pointer(root_schema, pointer)
    if not isinstance(resolved, dict):
        raise ValueError(f"$ref does not resolve to an object schema: {ref}")
    return resolved


def _branch_matches(
    branch: Any,
    data: Any,
    path: str,
    root_schema: dict[str, Any],
    ref_depth: int,
) -> bool:
    if not isinstance(branch, dict):
        return False
    return not validate_minimal(branch, data, path, root_schema=root_schema, _ref_depth=ref_depth)


def validate_minimal(
    schema: dict[str, Any],
    data: Any,
    path: str = "$",
    *,
    root_schema: dict[str, Any] | None = None,
    _ref_depth: int = 0,
) -> list[str]:
    """Validate the repository's JSON Schema subset without third-party dependencies."""

    errors: list[str] = []
    root_schema = root_schema or schema

    ref = schema.get("$ref")
    if ref is not None:
        if not isinstance(ref, str):
            errors.append(f"{path}: $ref must be a string")
        elif _ref_depth >= 100:
            errors.append(f"{path}: $ref nesting exceeds 100")
        else:
            try:
                resolved = _resolve_local_ref(root_schema, ref)
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                errors.append(f"{path}: invalid $ref {ref!r}: {exc}")
            else:
                errors.extend(
                    validate_minimal(
                        resolved,
                        data,
                        path,
                        root_schema=root_schema,
                        _ref_depth=_ref_depth + 1,
                    )
                )

    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        for index, branch in enumerate(all_of):
            if not isinstance(branch, dict):
                errors.append(f"{path}: allOf[{index}] must be an object schema")
                continue
            errors.extend(validate_minimal(branch, data, path, root_schema=root_schema, _ref_depth=_ref_depth))

    any_of = schema.get("anyOf")
    if isinstance(any_of, list) and not any(
        _branch_matches(branch, data, path, root_schema, _ref_depth) for branch in any_of
    ):
        errors.append(f"{path}: value does not match anyOf")

    one_of = schema.get("oneOf")
    if isinstance(one_of, list):
        matches = sum(_branch_matches(branch, data, path, root_schema, _ref_depth) for branch in one_of)
        if matches != 1:
            errors.append(f"{path}: value matches {matches} oneOf branches; expected exactly 1")

    not_schema = schema.get("not")
    if isinstance(not_schema, dict) and _branch_matches(not_schema, data, path, root_schema, _ref_depth):
        errors.append(f"{path}: value matches forbidden not schema")

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
        if isinstance(properties, dict):
            for key, subschema in properties.items():
                if key in data and isinstance(subschema, dict):
                    errors.extend(
                        validate_minimal(
                            subschema,
                            data[key],
                            f"{path}.{key}",
                            root_schema=root_schema,
                            _ref_depth=_ref_depth,
                        )
                    )

        additional = schema.get("additionalProperties", True)
        known_keys = set(properties) if isinstance(properties, dict) else set()
        for key in data.keys() - known_keys:
            if additional is False:
                errors.append(f"{path}.{key}: additional property is not allowed")
            elif isinstance(additional, dict):
                errors.extend(
                    validate_minimal(
                        additional,
                        data[key],
                        f"{path}.{key}",
                        root_schema=root_schema,
                        _ref_depth=_ref_depth,
                    )
                )

        if "minProperties" in schema and len(data) < int(schema["minProperties"]):
            errors.append(f"{path}: fewer than minProperties {schema['minProperties']}")
        if "maxProperties" in schema and len(data) > int(schema["maxProperties"]):
            errors.append(f"{path}: more than maxProperties {schema['maxProperties']}")

    if isinstance(data, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(data):
                errors.extend(
                    validate_minimal(
                        item_schema,
                        item,
                        f"{path}[{index}]",
                        root_schema=root_schema,
                        _ref_depth=_ref_depth,
                    )
                )
        if "minItems" in schema and len(data) < int(schema["minItems"]):
            errors.append(f"{path}: fewer than minItems {schema['minItems']}")
        if "maxItems" in schema and len(data) > int(schema["maxItems"]):
            errors.append(f"{path}: more than maxItems {schema['maxItems']}")
        if schema.get("uniqueItems"):
            serialized = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in data]
            if len(serialized) != len(set(serialized)):
                errors.append(f"{path}: array items are not unique")

    if isinstance(data, str):
        if "minLength" in schema and len(data) < int(schema["minLength"]):
            errors.append(f"{path}: shorter than minLength {schema['minLength']}")
        if "maxLength" in schema and len(data) > int(schema["maxLength"]):
            errors.append(f"{path}: longer than maxLength {schema['maxLength']}")
        if "pattern" in schema:
            try:
                matched = re.search(str(schema["pattern"]), data)
            except re.error as exc:
                errors.append(f"{path}: schema pattern is invalid: {exc}")
            else:
                if matched is None:
                    errors.append(f"{path}: does not match pattern {schema['pattern']!r}")

    if isinstance(data, (int, float)) and not isinstance(data, bool):
        if not math.isfinite(float(data)):
            errors.append(f"{path}: number must be finite")
        if "minimum" in schema and data < schema["minimum"]:
            errors.append(f"{path}: less than minimum {schema['minimum']}")
        if "maximum" in schema and data > schema["maximum"]:
            errors.append(f"{path}: greater than maximum {schema['maximum']}")
        if "exclusiveMinimum" in schema and data <= schema["exclusiveMinimum"]:
            errors.append(f"{path}: not greater than exclusiveMinimum {schema['exclusiveMinimum']}")
        if "exclusiveMaximum" in schema and data >= schema["exclusiveMaximum"]:
            errors.append(f"{path}: not less than exclusiveMaximum {schema['exclusiveMaximum']}")
        if "multipleOf" in schema:
            divisor = float(schema["multipleOf"])
            if divisor <= 0 or not math.isclose(float(data) / divisor, round(float(data) / divisor)):
                errors.append(f"{path}: not a multiple of {schema['multipleOf']}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local JSON against the Inward Eyes schema subset.")
    parser.add_argument("--schema", required=True)
    parser.add_argument("--json", required=True)
    parser.add_argument("--pointer", help="Optional JSON Pointer selecting a nested value to validate.")
    args = parser.parse_args()

    try:
        schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))
        data = json.loads(Path(args.json).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"input read failed: {exc}")
        return 1
    if not isinstance(schema, dict):
        print("schema root must be an object")
        return 1
    if args.pointer:
        try:
            data = resolve_pointer(data, args.pointer)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
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
