from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any


def _schema_block(root: Path) -> dict[str, Any]:
    schema = json.loads((root / "schemas" / "document_ast.schema.json").read_text(encoding="utf-8"))
    return schema["properties"]["document"]["properties"]["blocks"]["items"]


def _skill_block_types(text: str) -> set[str]:
    marker = "Allowed block types:"
    if marker not in text:
        return set()
    tail = text.split(marker, 1)[1]
    found: list[str] = []
    for line in tail.splitlines():
        match = re.fullmatch(r"\s*-\s+`([^`]+)`\s*", line)
        if match:
            found.append(match.group(1))
        elif found and line.strip():
            break
    return set(found)


def _skill_thread_example(text: str) -> dict[str, Any] | None:
    marker = "Minimum `thread_post` fields:"
    if marker not in text:
        return None
    match = re.search(r"```json\s*(\{.*?\})\s*```", text.split(marker, 1)[1], re.DOTALL)
    if not match:
        return None
    loaded = json.loads(match.group(1))
    return loaded if isinstance(loaded, dict) else None


def _renderer_block_types(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare) or len(node.ops) != 1 or len(node.comparators) != 1:
            continue
        if not isinstance(node.left, ast.Name) or node.left.id != "block_type":
            continue
        comparator = node.comparators[0]
        if isinstance(node.ops[0], ast.Eq) and isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
            found.add(comparator.value)
    return found


def validate_contract_drift(root: Path) -> list[str]:
    errors: list[str] = []
    skill_path = root / "skills" / "page-to-md" / "SKILL.md"
    renderer_path = root / "scripts" / "inward_eyes" / "markdown.py"
    skill_text = skill_path.read_text(encoding="utf-8")
    block_schema = _schema_block(root)
    schema_types = set(block_schema["properties"]["type"]["enum"])
    skill_types = _skill_block_types(skill_text)
    renderer_types = _renderer_block_types(renderer_path)
    if skill_types != schema_types:
        errors.append(f"AST_BLOCK_TYPE_DRIFT:skill={sorted(skill_types)} schema={sorted(schema_types)}")
    if renderer_types != schema_types:
        errors.append(f"AST_BLOCK_TYPE_DRIFT:renderer={sorted(renderer_types)} schema={sorted(schema_types)}")

    example = _skill_thread_example(skill_text)
    if example is None:
        errors.append("AST_THREAD_EXAMPLE_MISSING")
    else:
        if example.get("type") != "thread_post":
            errors.append("AST_THREAD_EXAMPLE_TYPE_INVALID")
        if not isinstance(example.get("author"), (str, type(None))):
            errors.append("AST_THREAD_AUTHOR_MUST_BE_STRING_OR_NULL")
        if not isinstance(example.get("published_at"), (str, type(None))):
            errors.append("AST_THREAD_PUBLISHED_AT_MUST_BE_STRING_OR_NULL")
        if not isinstance(example.get("body_blocks"), list):
            errors.append("AST_THREAD_BODY_BLOCKS_MUST_BE_ARRAY")
        for field in ("author", "published_at"):
            allowed = set(block_schema["properties"][field]["type"])
            if allowed != {"string", "null"}:
                errors.append(f"AST_THREAD_SCHEMA_TYPE_DRIFT:{field}={sorted(allowed)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check page-to-md skill, AST schema, and renderer for drift.")
    parser.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parents[2]))
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        errors = validate_contract_drift(root)
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError, SyntaxError) as exc:
        errors = [f"AST_DRIFT_CHECK_FAILED:{exc.__class__.__name__}:{exc}"]
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
