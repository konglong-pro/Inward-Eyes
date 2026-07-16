from __future__ import annotations

import argparse
import ipaddress
import json
import re
import socket
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.capture import (
    build_page_capture,
    claim_page_workflow_ownership,
    screenshot_file_is_valid,
    validate_page_capture_contract,
    write_capture_stage_manifest,
    write_capture_warnings,
)
from inward_eyes.io import utc_now, write_bytes, write_json
from inward_eyes.paths import prepare_run_dir
from inward_eyes.safety import classify_action


def _slug_timestamp(timestamp: str) -> str:
    return re.sub(r"[^0-9TZ]", "", timestamp).replace("Z", "Z")


def _read_optional_text(path: str | None) -> str | None:
    if not path:
        return None
    return Path(path).read_text(encoding="utf-8")


def _read_optional_json(path: str | None) -> Any:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_optional_json_or_text(json_path: str | None, text_path: str | None) -> Any:
    if json_path:
        return _read_optional_json(json_path)
    return _read_optional_text(text_path)


def _public_url_resolution(
    raw_url: str,
    *,
    resolve_dns: bool = True,
) -> tuple[str | None, list[ipaddress.IPv4Address | ipaddress.IPv6Address]]:
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return "public_http_url_required", []
    hostname = parsed.hostname.lower()
    if hostname in {"localhost", "127.0.0.1", "::1"} or hostname.endswith(".local"):
        return "public_url_required", []
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        if not resolve_dns:
            return None, []
        try:
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            resolved = {
                record[4][0]
                for record in socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
                if record and record[4]
            }
        except (OSError, ValueError):
            return "public_url_dns_resolution_failed", []
        if not resolved:
            return "public_url_dns_resolution_failed", []
        try:
            addresses = [ipaddress.ip_address(value) for value in resolved]
        except ValueError:
            return "public_url_dns_resolution_failed", []
        if any(not value.is_global for value in addresses):
            return "public_url_resolves_non_public", []
        return None, sorted(addresses, key=lambda value: (value.version, int(value)))
    if not address.is_global:
        return "public_url_required", []
    return None, [address]


def _public_url_error(raw_url: str, *, resolve_dns: bool = True) -> str | None:
    error, _ = _public_url_resolution(raw_url, resolve_dns=resolve_dns)
    return error


def _public_url_pin(raw_url: str) -> tuple[str | None, str | None]:
    error, addresses = _public_url_resolution(raw_url, resolve_dns=True)
    if error:
        return None, error
    if not addresses:
        return None, "public_url_dns_resolution_failed"
    return str(addresses[0]), None


def _request_url_error(initial_url: str, request_url: str, *, is_document: bool) -> str | None:
    approved_host = (urlparse(initial_url).hostname or "").lower()
    request_host = (urlparse(request_url).hostname or "").lower()
    if request_host != approved_host:
        return "redirect_domain_not_approved" if is_document else "request_domain_not_approved"
    return _public_url_error(request_url)


def _final_url_error(initial_url: str, final_url: str, *, resolve_dns: bool = True) -> str | None:
    public_error = _public_url_error(final_url, resolve_dns=resolve_dns)
    if public_error:
        return f"final_url_blocked:{public_error}"
    if (urlparse(final_url).hostname or "").lower() != (urlparse(initial_url).hostname or "").lower():
        return "final_url_domain_not_approved"
    return None


def _safe_asset_name(raw_name: str, index: int) -> str:
    path = Path(raw_name)
    suffix = path.suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        suffix = ".png"
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", path.stem).strip(".-") or f"screenshot-{index:03d}"
    return f"{index:03d}-{stem}{suffix}"


def _stage_screenshots(raw_paths: list[str], run_dir: Path) -> tuple[list[str], list[str]]:
    staged: list[str] = []
    warnings: list[str] = []
    for index, raw_path in enumerate(raw_paths, start=1):
        source = Path(raw_path).resolve()
        if not screenshot_file_is_valid(source):
            warnings.append(f"screenshot_asset_missing_or_invalid:{index}")
            continue
        destination = run_dir / "capture" / "screenshots" / _safe_asset_name(raw_path, index)
        write_bytes(destination, source.read_bytes())
        if not screenshot_file_is_valid(destination):
            destination.unlink(missing_ok=True)
            warnings.append(f"screenshot_asset_copy_invalid:{index}")
            continue
        staged.append(f"screenshots/{destination.name}")
    return staged, warnings


def _has_observation_payload(
    html: str | None,
    text: str | None,
    selected_main_content: str | None,
    accessibility_snapshot: Any,
) -> bool:
    return any(
        value is not None and (not isinstance(value, str) or bool(value.strip()))
        for value in (html, text, selected_main_content, accessibility_snapshot)
    )


def _extract_with_local_playwright(args: argparse.Namespace) -> tuple[dict[str, Any] | None, str | None]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - depends on optional local dependency
        return None, f"playwright_python_unavailable:{exc.__class__.__name__}"

    pinned_ip, pin_error = _public_url_pin(args.url)
    if pin_error or pinned_ip is None:
        return None, f"public_url_pin_failed:{pin_error or 'unknown'}"
    approved_host = (urlparse(args.url).hostname or "").lower()
    resolver_target = f"[{pinned_ip}]" if ":" in pinned_ip else pinned_ip

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=[
                    f"--host-resolver-rules=MAP {approved_host} {resolver_target}, EXCLUDE localhost",
                    "--no-proxy-server",
                    "--disable-quic",
                    "--disable-background-networking",
                    "--disable-preconnect",
                    "--dns-prefetch-disable",
                ],
            )
            try:
                context = browser.new_context(
                    viewport={"width": args.viewport_width, "height": args.viewport_height},
                    java_script_enabled=True,
                    service_workers="block",
                )
                context.add_init_script(
                    """
                    for (const name of ["WebSocket", "WebTransport", "RTCPeerConnection", "webkitRTCPeerConnection"]) {
                      if (name in globalThis) {
                        Object.defineProperty(globalThis, name, {
                          configurable: false,
                          value: class BlockedNetworkAPI {
                            constructor() {
                              throw new DOMException(`${name} blocked by capture policy`, "SecurityError");
                            }
                          }
                        });
                      }
                    }
                    """
                )
                blocked_requests: list[str] = []
                def route_request(route: Any, request: Any) -> None:
                    request_url = str(request.url)
                    # Resolve at dispatch time for every request. Reusing the
                    # first DNS answer would leave a DNS-rebinding window later
                    # in the same browser session.
                    error = _request_url_error(
                        args.url,
                        request_url,
                        is_document=request.resource_type == "document",
                    )
                    if error:
                        blocked_requests.append(f"{error}:{request_url}")
                        route.abort("blockedbyclient")
                    else:
                        route.continue_()

                context.route("**/*", route_request)
                page = context.new_page()
                if hasattr(page, "route_web_socket"):
                    page.route_web_socket(
                        "**/*",
                        lambda websocket: websocket.close(code=1008, reason="blocked by capture policy"),
                    )
                page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout_ms)
                try:
                    page.wait_for_load_state("networkidle", timeout=min(args.timeout_ms, 5000))
                except Exception:
                    pass
                final_url = str(page.url)
                final_url_error = _final_url_error(args.url, final_url)
                if blocked_requests:
                    return None, "public_url_request_blocked"
                if final_url_error:
                    return None, final_url_error
                observed = page.evaluate(
                    """() => {
                        const main = document.querySelector("main, article, [role='main']") || document.body;
                        const canonical = document.querySelector('link[rel="canonical"]');
                        const siteName =
                          document.querySelector('meta[property="og:site_name"]') ||
                          document.querySelector('meta[name="application-name"]');
                        return {
                          title: document.title || null,
                          canonical_url: canonical ? canonical.href : null,
                          site_name: siteName ? siteName.content : null,
                          html: main ? main.outerHTML : document.documentElement.outerHTML,
                          text: document.body ? document.body.innerText : null,
                          selected_main_content: main ? main.innerText : null
                        };
                    }"""
                )
                observed["final_url"] = final_url
                if args.screenshot_required:
                    observed["screenshot_bytes"] = page.screenshot(type="png", full_page=True)
            finally:
                browser.close()
            return observed, None
    except Exception as exc:  # pragma: no cover - depends on live browser/network state
        return None, f"playwright_capture_failed:{exc.__class__.__name__}"


def _failure_report(reason: str, screenshot_reason: str = "capture_failed") -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "status": "fail",
        "errors": [reason],
        "warnings": [reason],
        "requires_manual_review": True,
        "screenshot_policy": {"required": False, "reason": screenshot_reason, "status": "capture_failed"},
        "run_status": "failed",
        "validation_status": "failed",
        "manual_review": {
            "required": True,
            "severity": "blocking",
            "reasons": [
                {
                    "code": reason,
                    "message": reason.replace("_", " "),
                    "severity": "blocking",
                    "artifact": "capture/page_capture.json",
                }
            ],
        },
        "completion_blockers": [reason],
    }


def _write_failure_run(
    run_dir: Path,
    *,
    run_id: str,
    started_at: str,
    input_record: dict[str, Any],
    report: dict[str, Any],
    aborted_by_policy: bool = False,
) -> None:
    write_json(run_dir / "input.json", input_record)
    write_json(run_dir / "validation" / "capture-validation-report.json", report)
    write_capture_warnings(run_dir / "validation" / "warnings.md", report.get("warnings", []))
    write_capture_stage_manifest(
        run_dir,
        run_id=run_id,
        started_at=started_at,
        finished_at=utc_now(),
        input_record=input_record,
        report=report,
        capture_written=False,
        aborted_by_policy=aborted_by_policy,
    )


def run(args: argparse.Namespace) -> Path:
    started_at = utc_now()
    run_id = args.run_id or f"{_slug_timestamp(started_at)}-playwright-mcp-capture"
    html = args.html if args.html is not None else _read_optional_text(args.html_file)
    text = args.text if args.text is not None else _read_optional_text(args.text_file)
    selected_main_content = (
        args.selected_main_content
        if args.selected_main_content is not None
        else _read_optional_text(args.selected_main_content_file)
    )
    accessibility_snapshot = _read_optional_json_or_text(
        args.accessibility_snapshot_json,
        args.accessibility_snapshot_file,
    )
    for raw_path in args.screenshot:
        screenshot_file_is_valid(Path(raw_path).resolve())
    run_dir = prepare_run_dir(args.output_root or "browser-operator-runs", run_id)
    claim_page_workflow_ownership(
        run_dir,
        run_id=run_id,
        ownership_token=getattr(args, "wrapper_ownership_token", None),
    )

    parsed_url = urlparse(args.url)
    input_record: dict[str, Any] = {
        "target_url": args.url,
        "allowed_domain": parsed_url.hostname,
        "final_url": None,
        "backend": "playwright_mcp",
        "workflow": "page-to-md",
        "capture_stage": "browser_adapter",
        "requires_login": bool(args.requires_login),
        "actions": ["open_url", "read_visible_text", "save_artifacts", *args.action],
    }

    has_declared_observation = bool(
        args.failure_reason
        or args.html is not None
        or args.html_file
        or args.text is not None
        or args.text_file
        or args.selected_main_content is not None
        or args.selected_main_content_file
        or args.accessibility_snapshot_json
        or args.accessibility_snapshot_file
    )
    public_url_error = _public_url_error(args.url, resolve_dns=not has_declared_observation)
    if public_url_error:
        report = _failure_report(public_url_error, "capture_failed")
        _write_failure_run(
            run_dir,
            run_id=run_id,
            started_at=started_at,
            input_record=input_record,
            report=report,
            aborted_by_policy=True,
        )
        print(run_dir)
        return run_dir

    for action in input_record["actions"]:
        decision = classify_action(str(action))
        if not decision.allowed:
            report = _failure_report(f"policy_blocked:{decision.classification}:{decision.action}", "policy_blocked")
            _write_failure_run(
                run_dir,
                run_id=run_id,
                started_at=started_at,
                input_record={**input_record, "policy_decision": decision.__dict__},
                report=report,
                aborted_by_policy=True,
            )
            print(run_dir)
            return run_dir

    if args.requires_login:
        report = _failure_report("logged_in_capture_out_of_scope", "requires_login")
        _write_failure_run(
            run_dir,
            run_id=run_id,
            started_at=started_at,
            input_record=input_record,
            report=report,
            aborted_by_policy=True,
        )
        print(run_dir)
        return run_dir

    if args.failure_reason:
        report = _failure_report(str(args.failure_reason))
        _write_failure_run(run_dir, run_id=run_id, started_at=started_at, input_record=input_record, report=report)
        print(run_dir)
        return run_dir

    effective_url = args.url
    live_screenshot_bytes: bytes | None = None
    if not _has_observation_payload(html, text, selected_main_content, accessibility_snapshot):
        observed, failure = _extract_with_local_playwright(args)
        if failure:
            report = _failure_report(failure)
            _write_failure_run(run_dir, run_id=run_id, started_at=started_at, input_record=input_record, report=report)
            print(run_dir)
            return run_dir
        if isinstance(observed, dict):
            screenshot_value = observed.pop("screenshot_bytes", None)
            if isinstance(screenshot_value, bytes):
                live_screenshot_bytes = screenshot_value
            effective_url = str(observed.get("final_url") or args.url)
            html = observed.get("html")
            text = observed.get("text")
            selected_main_content = observed.get("selected_main_content")
            args.page_title = args.page_title or observed.get("title")
            args.canonical_url = args.canonical_url or observed.get("canonical_url")
            args.site_name = args.site_name or observed.get("site_name")
    final_url_error = _final_url_error(
        args.url,
        effective_url,
        resolve_dns=not has_declared_observation,
    )
    if final_url_error:
        report = _failure_report(final_url_error)
        _write_failure_run(run_dir, run_id=run_id, started_at=started_at, input_record=input_record, report=report)
        print(run_dir)
        return run_dir
    input_record["final_url"] = effective_url
    input_record["allowed_domains"] = [parsed_url.hostname] if parsed_url.hostname else []

    screenshot_paths, screenshot_warnings = _stage_screenshots([str(path) for path in args.screenshot], run_dir)
    if live_screenshot_bytes is not None:
        live_screenshot_path = run_dir / "capture" / "screenshots" / "live-page.png"
        write_bytes(live_screenshot_path, live_screenshot_bytes)
        if screenshot_file_is_valid(live_screenshot_path):
            screenshot_paths.append("screenshots/live-page.png")
        else:
            live_screenshot_path.unlink(missing_ok=True)
            screenshot_warnings.append("live_screenshot_invalid")

    capture = build_page_capture(
        url=effective_url,
        page_title=args.page_title,
        html=html,
        text=text,
        accessibility_snapshot=accessibility_snapshot,
        selected_main_content=selected_main_content,
        canonical_url=args.canonical_url,
        site_name=args.site_name,
        capture_id=args.capture_id,
        capture_method=args.capture_method,
        browser_tool="playwright_mcp",
        login_state="not_required",
        requires_login=False,
        user_visible_profile=False,
        region_or_locale=args.region_or_locale,
        viewport={"width": args.viewport_width, "height": args.viewport_height},
        screenshot_paths=screenshot_paths,
        screenshot_required=args.screenshot_required,
        screenshot_reason=args.screenshot_reason,
        warnings=list(dict.fromkeys(list(args.warning) + screenshot_warnings)),
    )
    report = validate_page_capture_contract(capture)

    write_json(run_dir / "input.json", input_record)
    write_json(run_dir / "capture" / "page_capture.json", capture)
    write_json(run_dir / "validation" / "capture-validation-report.json", report)
    write_capture_warnings(run_dir / "validation" / "warnings.md", report.get("warnings", []))
    write_capture_stage_manifest(
        run_dir,
        run_id=run_id,
        started_at=started_at,
        finished_at=utc_now(),
        input_record=input_record,
        report=report,
        capture_written=True,
    )
    print(run_dir)
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Write a page_capture.json from Playwright MCP observations or optional local Playwright capture. "
            "This script does not enable MCP by default or attach a user browser profile."
        )
    )
    parser.add_argument("--url", required=True, help="Public article/docs URL captured by the browser tool.")
    parser.add_argument("--output-root", default="browser-operator-runs")
    parser.add_argument("--run-id")
    parser.add_argument("--wrapper-ownership-token", help=argparse.SUPPRESS)
    parser.add_argument("--capture-id")
    parser.add_argument("--page-title")
    parser.add_argument("--canonical-url")
    parser.add_argument("--site-name")
    parser.add_argument("--html")
    parser.add_argument("--html-file")
    parser.add_argument("--text")
    parser.add_argument("--text-file")
    parser.add_argument("--selected-main-content")
    parser.add_argument("--selected-main-content-file")
    parser.add_argument("--accessibility-snapshot-json")
    parser.add_argument("--accessibility-snapshot-file")
    parser.add_argument("--capture-method", default="playwright_mcp_dom_snapshot")
    parser.add_argument("--region-or-locale")
    parser.add_argument("--viewport-width", type=int, default=1440)
    parser.add_argument("--viewport-height", type=int, default=1200)
    parser.add_argument("--timeout-ms", type=int, default=15000)
    parser.add_argument("--screenshot", action="append", default=[], help="Relative screenshot evidence path.")
    parser.add_argument("--screenshot-required", action="store_true")
    parser.add_argument("--screenshot-reason", default="static_public_article")
    parser.add_argument("--warning", action="append", default=[])
    parser.add_argument("--action", action="append", default=[], help="Additional browser action to classify.")
    parser.add_argument("--requires-login", action="store_true", help="Abort: logged-in capture is out of M6 scope.")
    parser.add_argument("--failure-reason", help="Write an auditable failed capture run without page artifacts.")
    args = parser.parse_args()
    run_dir = run(args)
    report_path = run_dir / "validation" / "capture-validation-report.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        return 0 if report.get("status") == "pass" else 1
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    return 0 if manifest.get("run_status") == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
