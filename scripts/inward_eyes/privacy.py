from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from inward_eyes.capture import FORBIDDEN_CAPTURE_KEYS


TEXT_EXTENSIONS = {".json", ".md", ".csv", ".txt"}
PRIVATE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email_address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("phone_number", re.compile(r"(?<!\d)(?:\+?\d[\d .()-]{7,}\d)(?!\d)")),
    ("api_key_like", re.compile(r"\b(?:sk|pk|ghp|gho|ghu|ghs)_[A-Za-z0-9_]{12,}\b")),
    ("credit_card_like", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
)


def _redacted_sample(value: str, pattern: re.Pattern[str]) -> str:
    match = pattern.search(value)
    if not match:
        return ""
    text = match.group(0)
    if len(text) <= 6:
        return "[redacted]"
    return f"{text[:2]}[redacted]{text[-2:]}"


def _scan_value(value: Any, path: str, findings: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if str(key).lower() in FORBIDDEN_CAPTURE_KEYS:
                findings.append(
                    {
                        "code": f"PRIVACY_FORBIDDEN_KEY:{key}",
                        "path": child_path,
                        "severity": "blocking",
                        "sample": "",
                    }
                )
            _scan_value(nested, child_path, findings)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _scan_value(nested, f"{path}[{index}]", findings)
    elif isinstance(value, str):
        for label, pattern in PRIVATE_PATTERNS:
            if pattern.search(value):
                findings.append(
                    {
                        "code": f"PRIVACY_PRIVATE_TEXT:{label}",
                        "path": path,
                        "severity": "warning",
                        "sample": _redacted_sample(value, pattern),
                    }
                )


def scan_document(data: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    _scan_value(data, "", findings)
    return findings


def _read_text_or_json(path: Path) -> Any:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return path.read_text(encoding="utf-8")


def _iter_scan_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() in TEXT_EXTENSIONS else []
    files: list[Path] = []
    for candidate in path.rglob("*"):
        if candidate.is_file() and candidate.suffix.lower() in TEXT_EXTENSIONS:
            files.append(candidate)
    return sorted(files)


def build_privacy_report(path: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    scanned_files: list[str] = []
    root = path if path.is_dir() else path.parent
    for file_path in _iter_scan_files(path):
        try:
            data = _read_text_or_json(file_path)
        except Exception as exc:
            findings.append(
                {
                    "code": f"PRIVACY_SCAN_READ_FAILED:{exc.__class__.__name__}",
                    "path": file_path.as_posix(),
                    "severity": "warning",
                    "sample": "",
                }
            )
            continue
        scanned_files.append(file_path.resolve().relative_to(root.resolve()).as_posix())
        for finding in scan_document(data):
            findings.append(
                {
                    **finding,
                    "file": file_path.resolve().relative_to(root.resolve()).as_posix(),
                }
            )
    blockers = [item["code"] for item in findings if item.get("severity") == "blocking"]
    warnings = [item["code"] for item in findings if item.get("severity") != "blocking"]
    return {
        "schema_version": "1.0",
        "target": str(path),
        "scanned_files": scanned_files,
        "findings": findings,
        "status": "fail" if blockers else "pass",
        "errors": blockers,
        "warnings": warnings,
        "requires_manual_review": bool(findings),
        "run_status": "failed" if blockers else "partial" if findings else "complete",
        "validation_status": "failed" if blockers else "passed",
        "manual_review": {
            "required": bool(findings),
            "severity": "blocking" if blockers else "warning" if findings else "info",
            "reasons": [
                {
                    "code": item["code"],
                    "message": item["code"].replace("_", " ").replace(":", ": "),
                    "severity": item.get("severity", "warning"),
                    "artifact": item.get("file", str(path)),
                }
                for item in findings
            ],
        },
        "completion_blockers": blockers,
    }


def render_privacy_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Privacy Report",
        "",
        f"Status: `{report['status']}`",
        f"Run status: `{report['run_status']}`",
        f"Files scanned: {len(report.get('scanned_files', []))}",
        "",
    ]
    if not report.get("findings"):
        lines.append("No privacy findings.")
        return "\n".join(lines).rstrip() + "\n"
    lines.extend(["## Findings", ""])
    for finding in report["findings"]:
        sample = f" sample={finding['sample']}" if finding.get("sample") else ""
        lines.append(
            f"- {finding.get('severity', 'warning')}: {finding['code']} "
            f"at {finding.get('file', '')}:{finding.get('path', '')}{sample}"
        )
    return "\n".join(lines).rstrip() + "\n"
