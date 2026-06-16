from __future__ import annotations

from pathlib import Path
from typing import Any


ADAPTERS: list[dict[str, Any]] = [
    {
        "adapter_id": "local_html_input",
        "workflow": "page-to-md",
        "backend": "local_file",
        "entrypoint": "scripts/page_to_md_runner.py",
        "eval": "evals/run_eval.py",
        "scope": "local HTML or saved page input",
        "login_support": "not_applicable",
        "screenshot_support": "staged_from_input",
        "network_access": "none",
        "status": "stable",
        "limits": ["does not browse", "requires user-provided local input"],
    },
    {
        "adapter_id": "page_capture_json_input",
        "workflow": "page-to-md",
        "backend": "page_capture_json",
        "entrypoint": "scripts/page_to_md_runner.py",
        "eval": "evals/run_capture_adapter_eval.py",
        "scope": "pre-captured page_capture.json",
        "login_support": "declared_in_capture",
        "screenshot_support": "staged_from_capture",
        "network_access": "none",
        "status": "stable",
        "limits": ["does not browse", "capture contract validation is required"],
    },
    {
        "adapter_id": "playwright_mcp_public_url",
        "workflow": "page-to-md",
        "backend": "playwright_mcp",
        "entrypoint": "scripts/capture/playwright_mcp_capture.py",
        "eval": "evals/run_capture_adapter_eval.py",
        "scope": "one public HTTP(S) article/docs URL",
        "login_support": "forbidden",
        "screenshot_support": "optional_or_required_by_policy",
        "network_access": "bounded_public_url",
        "status": "stable",
        "limits": ["no logged-in capture", "no local/private URL capture"],
    },
    {
        "adapter_id": "current_chrome_visible_page",
        "workflow": "page-to-md",
        "backend": "current_chrome",
        "entrypoint": "scripts/capture/current_chrome_capture.py",
        "eval": "evals/run_capture_adapter_eval.py",
        "scope": "one explicitly user-approved visible Chrome page",
        "login_support": "approved_current_page_only",
        "screenshot_support": "required_for_login_private_dynamic_threads_forums_products",
        "network_access": "none_from_script",
        "status": "stable",
        "limits": ["no tab scanning", "no profile/session export", "no account-menu exploration"],
    },
    {
        "adapter_id": "research_provided_url_capture",
        "workflow": "browser-research",
        "backend": "provided_url_capture",
        "entrypoint": "scripts/research_capture_runner.py",
        "eval": "evals/run_research_capture_eval.py",
        "scope": "approved source URLs only",
        "login_support": "out_of_scope",
        "screenshot_support": "per_source_policy",
        "network_access": "approved_urls_only",
        "status": "stable",
        "limits": ["no search", "no recursive link following"],
    },
    {
        "adapter_id": "research_small_scope_discovery",
        "workflow": "browser-research",
        "backend": "bounded_discovery",
        "entrypoint": "scripts/research_discovery_runner.py",
        "eval": "evals/run_research_discovery_eval.py",
        "scope": "bounded public source candidate discovery",
        "login_support": "out_of_scope",
        "screenshot_support": "delegated_to_capture",
        "network_access": "bounded_public_search_scope",
        "status": "stable",
        "limits": ["max 20 selected sources", "accepted sources only are captured"],
    },
    {
        "adapter_id": "price_product_url_capture",
        "workflow": "price-compare",
        "backend": "provided_product_url_capture",
        "entrypoint": "scripts/price_capture_runner.py",
        "eval": "evals/run_price_capture_eval.py",
        "scope": "approved product URLs only",
        "login_support": "out_of_scope",
        "screenshot_support": "required_for_product_pages",
        "network_access": "approved_product_urls_only",
        "status": "stable",
        "limits": ["no cart", "no checkout", "no coupon claiming", "no address mutation"],
    },
    {
        "adapter_id": "price_candidate_discovery",
        "workflow": "price-compare",
        "backend": "approved_candidate_discovery",
        "entrypoint": "scripts/price_candidate_discovery_runner.py",
        "eval": "evals/run_price_candidate_discovery_eval.py",
        "scope": "approved ecommerce domains and candidate caps",
        "login_support": "out_of_scope",
        "screenshot_support": "delegated_to_quote_capture",
        "network_access": "approved_domains_only",
        "status": "stable",
        "limits": ["max 20 candidates", "no recommendations", "no marketplace-wide crawling"],
    },
]


def build_adapter_matrix(root: Path) -> dict[str, Any]:
    adapters: list[dict[str, Any]] = []
    for adapter in ADAPTERS:
        record = dict(adapter)
        record["entrypoint_exists"] = (root / record["entrypoint"]).exists()
        record["eval_exists"] = (root / record["eval"]).exists()
        adapters.append(record)
    return {
        "schema_version": "1.0",
        "matrix_id": "m12_adapter_matrix",
        "description": "Deterministic inventory of supported Inward Eyes adapter boundaries.",
        "adapters": adapters,
    }


def validate_adapter_matrix(matrix: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()
    adapters = matrix.get("adapters")
    if not isinstance(adapters, list) or not adapters:
        errors.append("ADAPTER_MATRIX_EMPTY")
        adapters = []
    for adapter in adapters:
        if not isinstance(adapter, dict):
            errors.append("ADAPTER_MATRIX_RECORD_NOT_OBJECT")
            continue
        adapter_id = str(adapter.get("adapter_id") or "")
        if not adapter_id:
            errors.append("ADAPTER_MATRIX_ID_MISSING")
        elif adapter_id in seen:
            errors.append(f"ADAPTER_MATRIX_DUPLICATE_ID:{adapter_id}")
        seen.add(adapter_id)
        for field in ("workflow", "backend", "entrypoint", "scope", "status"):
            if not adapter.get(field):
                errors.append(f"ADAPTER_MATRIX_FIELD_MISSING:{adapter_id}:{field}")
        if adapter.get("status") not in {"stable", "experimental", "planned"}:
            errors.append(f"ADAPTER_MATRIX_STATUS_INVALID:{adapter_id}:{adapter.get('status')}")
        if adapter.get("status") != "planned" and not adapter.get("entrypoint_exists"):
            errors.append(f"ADAPTER_MATRIX_ENTRYPOINT_MISSING:{adapter_id}:{adapter.get('entrypoint')}")
        if adapter.get("status") != "planned" and not adapter.get("eval_exists"):
            warnings.append(f"ADAPTER_MATRIX_EVAL_MISSING:{adapter_id}:{adapter.get('eval')}")
    status = "fail" if errors else "pass"
    return {
        "schema_version": "1.0",
        "status": status,
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
                    "artifact": "artifacts/adapter-matrix.json",
                }
                for code in errors + warnings
            ],
        },
        "completion_blockers": errors,
    }


def render_adapter_matrix_markdown(matrix: dict[str, Any], report: dict[str, Any]) -> str:
    lines = [
        "# Adapter Matrix",
        "",
        f"Status: `{report['status']}`",
        "",
        "| Adapter | Workflow | Backend | Scope | Login | Screenshots | Status |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for adapter in matrix.get("adapters", []):
        lines.append(
            "| {adapter_id} | {workflow} | {backend} | {scope} | {login_support} | "
            "{screenshot_support} | {status} |".format(**adapter)
        )
    lines.append("")
    if report.get("errors"):
        lines.extend(["## Blockers", ""])
        lines.extend(f"- {error}" for error in report["errors"])
        lines.append("")
    if report.get("warnings"):
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report["warnings"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
