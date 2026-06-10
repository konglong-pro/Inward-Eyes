from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import struct
import zlib
from typing import Any


MIN_MATCH_CONFIDENCE = 0.8
PRICE_KEYS = ("list_price", "sale_price", "coupon_price", "shipping_fee", "estimated_total")


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value) if str(item).strip()]


def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return text or "unknown"


def quote_evidence_name(quote: dict[str, Any]) -> str:
    platform = _slug(str(quote.get("platform") or "platform"))
    product = _slug(str(quote.get("product_identity", {}).get("product_name") or quote.get("quote_id") or "product"))
    return f"{platform}-{product}.png"


def source_dir_name(source_id: str) -> str:
    if source_id.startswith("S") and source_id[1:].isdigit():
        return f"source-{int(source_id[1:]):03d}"
    return source_id.lower().replace("_", "-")


def _number_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^0-9.\-]", "", value)
        if cleaned:
            try:
                return float(cleaned)
            except ValueError:
                return None
    return None


def _price_components(raw_quote: dict[str, Any]) -> dict[str, float | None]:
    raw_prices = raw_quote.get("prices") if isinstance(raw_quote.get("prices"), dict) else raw_quote
    return {key: _number_or_none(raw_prices.get(key)) for key in PRICE_KEYS}


def _canonical_hash(data: dict[str, Any]) -> str:
    payload = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _required_specs(input_record: dict[str, Any]) -> dict[str, Any]:
    product = input_record.get("product")
    if isinstance(product, dict) and isinstance(product.get("required_specs"), dict):
        return product["required_specs"]
    if isinstance(input_record.get("required_specs"), dict):
        return input_record["required_specs"]
    return {}


def _missing_or_mismatched_specs(required_specs: dict[str, Any], actual_specs: dict[str, Any]) -> list[str]:
    mismatches: list[str] = []
    for key, expected in required_specs.items():
        actual = actual_specs.get(key)
        if actual is None:
            mismatches.append(str(key))
            continue
        if str(actual).strip().lower() != str(expected).strip().lower():
            mismatches.append(str(key))
    return mismatches


def normalize_candidate(raw_candidate: dict[str, Any], index: int, required_specs: dict[str, Any]) -> dict[str, Any]:
    identity = raw_candidate.get("product_identity") if isinstance(raw_candidate.get("product_identity"), dict) else {}
    specs = raw_candidate.get("specs") if isinstance(raw_candidate.get("specs"), dict) else identity.get("specs")
    specs = specs if isinstance(specs, dict) else {}
    confidence = float(_number_or_none(raw_candidate.get("match_confidence")) or 0)
    mismatches = _missing_or_mismatched_specs(required_specs, specs)
    anomalies = _strings(raw_candidate.get("anomalies"))
    if mismatches and "incomplete_spec_match" not in anomalies:
        anomalies.append("incomplete_spec_match")
    if confidence < MIN_MATCH_CONFIDENCE and "low_confidence_match" not in anomalies:
        anomalies.append("low_confidence_match")

    return {
        "candidate_id": str(raw_candidate.get("candidate_id") or f"K{index:03d}"),
        "product_identity": {
            "product_name": identity.get("product_name") or raw_candidate.get("product_name"),
            "model_number": identity.get("model_number") or raw_candidate.get("model_number"),
            "specs": specs,
        },
        "platform": raw_candidate.get("platform"),
        "url": raw_candidate.get("url"),
        "seller": raw_candidate.get("seller"),
        "condition": raw_candidate.get("condition"),
        "provisional_price": _number_or_none(raw_candidate.get("provisional_price")),
        "currency": raw_candidate.get("currency"),
        "match_confidence": confidence,
        "manual_review_required": bool(raw_candidate.get("manual_review_required") or anomalies),
        "anomalies": anomalies,
    }


def _quote_flags(raw_quote: dict[str, Any]) -> dict[str, bool]:
    return {
        "coupon_action_required": bool(raw_quote.get("coupon_action_required")),
        "cart_required": bool(raw_quote.get("cart_required")),
        "checkout_required": bool(raw_quote.get("checkout_required")),
        "membership_required": bool(raw_quote.get("membership_required")),
        "address_change_required": bool(raw_quote.get("address_change_required")),
    }


def quote_context(quote: dict[str, Any]) -> dict[str, Any]:
    prices = quote.get("prices", {})
    return {
        "platform": quote.get("platform"),
        "region": quote.get("region"),
        "currency": quote.get("currency"),
        "seller_type": quote.get("seller_type"),
        "condition": quote.get("condition"),
        "selected_specs": quote.get("product_identity", {}).get("specs", {}),
        "membership_required": bool(quote.get("flags", {}).get("membership_required")),
        "coupon_action_required": bool(quote.get("flags", {}).get("coupon_action_required")),
        "cart_required": bool(quote.get("flags", {}).get("cart_required")),
        "checkout_required": bool(quote.get("flags", {}).get("checkout_required")),
        "shipping_known": prices.get("shipping_fee") is not None,
        "stock_status": quote.get("stock"),
    }


def estimated_total_details(quote: dict[str, Any]) -> dict[str, Any]:
    prices = quote.get("prices", {})
    warnings = []
    if quote.get("flags", {}).get("coupon_action_required"):
        warnings.append("coupon_action_required")
    if prices.get("estimated_total") is not None:
        amount = prices["estimated_total"]
        calculation = "page_visible_estimated_total"
        components = {"base": "estimated_total", "shipping_fee": prices.get("shipping_fee")}
    elif prices.get("sale_price") is not None and prices.get("shipping_fee") is not None:
        amount = float(prices["sale_price"]) + float(prices["shipping_fee"])
        calculation = "sale_price + shipping_fee"
        components = {"base": "sale_price", "shipping_fee": prices.get("shipping_fee")}
    elif prices.get("list_price") is not None and prices.get("shipping_fee") is not None:
        amount = float(prices["list_price"]) + float(prices["shipping_fee"])
        calculation = "list_price + shipping_fee"
        components = {"base": "list_price", "shipping_fee": prices.get("shipping_fee")}
    else:
        amount = None
        calculation = "unknown"
        components = {"base": None, "shipping_fee": prices.get("shipping_fee")}
        warnings.append("estimated_total_unknown")
    return {
        "amount": amount,
        "currency": quote.get("currency"),
        "calculation": calculation,
        "components": components,
        "confidence": 0.9 if amount is not None and not warnings else 0.5 if amount is not None else 0,
        "warnings": warnings,
    }


def _default_screenshot_policy(raw_quote: dict[str, Any]) -> dict[str, Any]:
    if raw_quote.get("screenshot_fixture") or raw_quote.get("screenshot"):
        return {"required": True, "reason": "product_page", "status": "required_and_present"}
    return {"required": True, "reason": "product_page", "status": "required_but_missing"}


def normalize_quote(
    raw_quote: dict[str, Any],
    index: int,
    input_record: dict[str, Any],
    accessed_at: str,
    candidate_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    quote_id = str(raw_quote.get("quote_id") or f"Q{index:03d}")
    source_id = str(raw_quote.get("source_id") or f"S{index:03d}")
    candidate = candidate_by_id.get(str(raw_quote.get("candidate_id") or ""))
    identity = raw_quote.get("product_identity") if isinstance(raw_quote.get("product_identity"), dict) else {}
    if not identity and candidate:
        identity = candidate.get("product_identity", {})
    specs = raw_quote.get("specs") if isinstance(raw_quote.get("specs"), dict) else identity.get("specs")
    specs = specs if isinstance(specs, dict) else {}
    required_specs = _required_specs(input_record)
    confidence = float(_number_or_none(raw_quote.get("match_confidence")) or (candidate or {}).get("match_confidence") or 0)
    prices = _price_components(raw_quote)
    flags = _quote_flags(raw_quote)
    quote = {
        "quote_id": quote_id,
        "candidate_id": raw_quote.get("candidate_id"),
        "source_id": source_id,
        "source_record_path": f"evidence/{source_dir_name(source_id)}/source_record.json",
        "url": str(raw_quote.get("url") or (candidate or {}).get("url") or ""),
        "canonical_url": raw_quote.get("canonical_url"),
        "title": raw_quote.get("title") or identity.get("product_name") or raw_quote.get("product_name"),
        "platform": raw_quote.get("platform") or (candidate or {}).get("platform"),
        "region": raw_quote.get("region") or input_record.get("region"),
        "currency": raw_quote.get("currency") or input_record.get("currency"),
        "accessed_at": str(raw_quote.get("accessed_at") or accessed_at),
        "product_identity": {
            "product_name": identity.get("product_name") or raw_quote.get("product_name"),
            "model_number": identity.get("model_number") or raw_quote.get("model_number"),
            "specs": specs,
        },
        "seller": raw_quote.get("seller") or (candidate or {}).get("seller"),
        "seller_type": raw_quote.get("seller_type") or "unknown",
        "condition": raw_quote.get("condition") or (candidate or {}).get("condition"),
        "stock": raw_quote.get("stock") or "unknown",
        "prices": prices,
        "price_basis": raw_quote.get("price_basis") or "visible_page",
        "match_confidence": confidence,
        "selected_specs_confirmed": bool(raw_quote.get("selected_specs_confirmed")),
        "flags": flags,
        "screenshot_policy": raw_quote.get("screenshot_policy")
        if isinstance(raw_quote.get("screenshot_policy"), dict)
        else _default_screenshot_policy(raw_quote),
        "screenshot_fixture": bool(raw_quote.get("screenshot_fixture")),
        "warnings": _strings(raw_quote.get("warnings")),
        "notes": raw_quote.get("notes"),
        "anomalies": _strings(raw_quote.get("anomalies")),
    }
    screenshot = raw_quote.get("screenshot")
    if not screenshot and quote["screenshot_policy"].get("status") == "required_and_present":
        screenshot = f"evidence/{quote_evidence_name(quote)}"
    quote["screenshot"] = screenshot
    quote["anomalies"] = detect_quote_anomalies(quote, input_record)
    quote["quote_context"] = quote_context(quote)
    quote["quote_context_hash"] = _canonical_hash(quote["quote_context"])
    quote["estimated_total"] = estimated_total_details(quote)
    quote["comparison_price"] = comparison_price(quote)
    quote["manual_review_required"] = bool(quote.get("anomalies") or quote.get("flags", {}).get("coupon_action_required") or quote.get("flags", {}).get("cart_required") or quote.get("flags", {}).get("checkout_required") or quote.get("flags", {}).get("address_change_required"))
    quote["eligible_for_lowest_price"] = is_quote_eligible(quote)
    quote["excluded_from_lowest_price"] = not quote["eligible_for_lowest_price"]
    return quote


def detect_quote_anomalies(quote: dict[str, Any], input_record: dict[str, Any]) -> list[str]:
    anomalies = list(quote.get("anomalies") or [])
    required_specs = _required_specs(input_record)
    mismatches = _missing_or_mismatched_specs(required_specs, quote.get("product_identity", {}).get("specs", {}))
    if mismatches and "incomplete_spec_match" not in anomalies:
        anomalies.append("incomplete_spec_match")
    if quote.get("match_confidence", 0) < MIN_MATCH_CONFIDENCE and "low_confidence_match" not in anomalies:
        anomalies.append("low_confidence_match")
    if quote.get("seller_type") == "third_party" and "third_party_seller" not in anomalies:
        anomalies.append("third_party_seller")
    prices = quote.get("prices", {})
    visible_price = any(prices.get(key) is not None for key in ("list_price", "sale_price", "coupon_price", "estimated_total"))
    if quote.get("stock") == "out_of_stock" and visible_price and "out_of_stock_with_visible_price" not in anomalies:
        anomalies.append("out_of_stock_with_visible_price")
    if prices.get("shipping_fee") is None and "unknown_shipping_fee" not in anomalies:
        anomalies.append("unknown_shipping_fee")
    for flag_name, anomaly_name in (
        ("coupon_action_required", "coupon_action_required"),
        ("cart_required", "cart_required"),
        ("checkout_required", "checkout_required"),
        ("membership_required", "membership_required"),
        ("address_change_required", "region_or_address_change_required"),
    ):
        if quote.get("flags", {}).get(flag_name) and anomaly_name not in anomalies:
            anomalies.append(anomaly_name)
    expected_region = input_record.get("region")
    if expected_region and quote.get("region") and str(quote["region"]) != str(expected_region) and "region_mismatch" not in anomalies:
        anomalies.append("region_mismatch")
    if quote.get("warnings") and any("redirect" in warning or "expired" in warning for warning in quote["warnings"]):
        if "product_page_redirect_or_expiry" not in anomalies:
            anomalies.append("product_page_redirect_or_expiry")
    return anomalies


def comparison_price(quote: dict[str, Any]) -> float | None:
    prices = quote.get("prices", {})
    if prices.get("estimated_total") is not None:
        return prices["estimated_total"]
    base = prices.get("sale_price")
    if base is None:
        base = prices.get("list_price")
    shipping = prices.get("shipping_fee")
    if base is not None and shipping is not None:
        return float(base) + float(shipping)
    return None


def is_quote_eligible(quote: dict[str, Any]) -> bool:
    if quote.get("match_confidence", 0) < MIN_MATCH_CONFIDENCE:
        return False
    if not quote.get("selected_specs_confirmed"):
        return False
    if quote.get("stock") != "in_stock":
        return False
    if comparison_price(quote) is None:
        return False
    red_flags = ("coupon_action_required", "cart_required", "checkout_required", "address_change_required")
    if any(quote.get("flags", {}).get(flag) for flag in red_flags):
        return False
    if quote.get("manual_review_required"):
        return False
    if "incomplete_spec_match" in quote.get("anomalies", []):
        return False
    if quote.get("excluded_from_lowest_price"):
        return False
    return True


def build_price_model(input_record: dict[str, Any], generated_at: str) -> dict[str, Any]:
    required_specs = _required_specs(input_record)
    raw_candidates = [item for item in _as_list(input_record.get("candidates")) if isinstance(item, dict)]
    candidates = [normalize_candidate(candidate, index, required_specs) for index, candidate in enumerate(raw_candidates, start=1)]
    candidate_by_id = {candidate["candidate_id"]: candidate for candidate in candidates}
    raw_quotes = [item for item in _as_list(input_record.get("quotes")) if isinstance(item, dict)]
    quotes = [
        normalize_quote(quote, index, input_record, generated_at, candidate_by_id)
        for index, quote in enumerate(raw_quotes, start=1)
    ]
    eligible = [quote for quote in quotes if quote.get("eligible_for_lowest_price")]
    lowest = min(eligible, key=lambda quote: quote["comparison_price"]) if eligible else None
    return {
        "schema_version": "1.0",
        "task_type": "price-compare",
        "generated_at": generated_at,
        "comparison": {
            "title": input_record.get("title") or "Price comparison",
            "region": input_record.get("region"),
            "currency": input_record.get("currency"),
            "required_specs": required_specs,
            "min_match_confidence": MIN_MATCH_CONFIDENCE,
            "lowest_eligible_quote_id": lowest.get("quote_id") if lowest else None,
        },
        "candidates": candidates,
        "quotes": quotes,
        "anomalies": collect_anomalies(candidates, quotes),
        "warnings": _strings(input_record.get("warnings")),
    }


def collect_anomalies(candidates: list[dict[str, Any]], quotes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for candidate in candidates:
        for anomaly in candidate.get("anomalies") or []:
            records.append({"record_id": candidate["candidate_id"], "record_type": "candidate", "anomaly": anomaly})
    for quote in quotes:
        for anomaly in quote.get("anomalies") or []:
            records.append({"record_id": quote["quote_id"], "record_type": "quote", "anomaly": anomaly})
    return records


def source_record_from_quote(quote: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": quote["source_id"],
        "url": quote["url"],
        "canonical_url": quote.get("canonical_url"),
        "title": quote.get("title"),
        "site_name": quote.get("platform"),
        "page_type": "product_page",
        "accessed_at": quote["accessed_at"],
        "requires_login": False,
        "capture_method": "price_compare_input",
        "evidence_status": "source_record_present",
        "evidence": {
            "screenshot": quote.get("screenshot"),
            "snapshot": None,
            "source_record": quote.get("source_record_path"),
        },
        "screenshot_policy": quote.get("screenshot_policy"),
        "content_scope": {
            "included": ["product_identity", "selected_specs", "seller", "price_components", "stock"],
            "excluded": ["ads", "recommendations", "cart", "checkout", "account_data"],
        },
        "warnings": quote.get("warnings") or [],
    }


def render_prices_csv(quotes: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    fieldnames = [
        "quote_id",
        "source_id",
        "platform",
        "product_name",
        "seller",
        "seller_type",
        "condition",
        "region",
        "currency",
        "stock",
        "match_confidence",
        "list_price",
        "sale_price",
        "coupon_price",
                "shipping_fee",
                "estimated_total",
                "estimated_total_calculation",
                "quote_context_hash",
                "comparison_price",
                "manual_review_required",
                "excluded_from_lowest_price",
                "eligible_for_lowest_price",
                "url",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for quote in quotes:
        prices = quote.get("prices", {})
        writer.writerow(
            {
                "quote_id": quote.get("quote_id"),
                "source_id": quote.get("source_id"),
                "platform": quote.get("platform"),
                "product_name": quote.get("product_identity", {}).get("product_name"),
                "seller": quote.get("seller"),
                "seller_type": quote.get("seller_type"),
                "condition": quote.get("condition"),
                "region": quote.get("region"),
                "currency": quote.get("currency"),
                "stock": quote.get("stock"),
                "match_confidence": quote.get("match_confidence"),
                "list_price": prices.get("list_price"),
                "sale_price": prices.get("sale_price"),
                "coupon_price": prices.get("coupon_price"),
                "shipping_fee": prices.get("shipping_fee"),
                "estimated_total": prices.get("estimated_total"),
                "estimated_total_calculation": quote.get("estimated_total", {}).get("calculation"),
                "quote_context_hash": quote.get("quote_context_hash"),
                "comparison_price": quote.get("comparison_price"),
                "manual_review_required": quote.get("manual_review_required"),
                "excluded_from_lowest_price": quote.get("excluded_from_lowest_price"),
                "eligible_for_lowest_price": quote.get("eligible_for_lowest_price"),
                "url": quote.get("url"),
            }
        )
    return output.getvalue()


def _money(value: Any, currency: str | None) -> str:
    if value is None:
        return "Unknown"
    prefix = "$" if currency == "USD" else f"{currency or ''} "
    return f"{prefix}{float(value):.2f}".strip()


def render_price_report(model: dict[str, Any]) -> str:
    comparison = model["comparison"]
    currency = comparison.get("currency")
    lines = [
        "---",
        f'title: "{comparison["title"]}"',
        'task_type: "price-compare"',
        f'generated_at: "{model["generated_at"]}"',
        "---",
        "",
        f"# {comparison['title']}",
        "",
        f"> Region: {comparison.get('region') or 'Unknown'}",
        f"> Currency: {currency or 'Unknown'}",
        "",
    ]
    lowest_id = comparison.get("lowest_eligible_quote_id")
    if lowest_id:
        lowest = next(quote for quote in model["quotes"] if quote["quote_id"] == lowest_id)
        lines.extend(
            [
                "## Lowest Eligible Quote",
                "",
                f"- Quote: **{lowest_id}**",
                f"- Platform: {lowest.get('platform') or 'Unknown'}",
                f"- Seller: {lowest.get('seller') or 'Unknown'}",
                f"- Estimated total: {_money(lowest.get('comparison_price'), currency)}",
                f"- Source: [{lowest.get('source_id')}]({lowest.get('url')})",
                "",
            ]
        )
    else:
        lines.extend(["## Lowest Eligible Quote", "", "No eligible final lowest quote. Manual review required.", ""])

    lines.extend(["## Quotes", ""])
    lines.append("| Quote | Platform | Seller | Stock | Match | Total | Calculation | Eligible | Source |")
    lines.append("| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |")
    for quote in model["quotes"]:
        lines.append(
            f"| {quote['quote_id']} | {quote.get('platform') or 'Unknown'} | {quote.get('seller') or 'Unknown'} | "
            f"{quote.get('stock') or 'Unknown'} | {quote.get('match_confidence', 0):.2f} | "
            f"{_money(quote.get('comparison_price'), currency)} | {quote.get('estimated_total', {}).get('calculation', 'unknown')} | "
            f"{quote.get('eligible_for_lowest_price')} | "
            f"[{quote.get('source_id')}]({quote.get('url')}) |"
        )
    lines.append("")

    if model["anomalies"]:
        lines.extend(["## Anomalies", ""])
        for anomaly in model["anomalies"]:
            lines.append(f"- {anomaly['record_id']}: {anomaly['anomaly']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_anomalies(model: dict[str, Any]) -> str:
    if not model["anomalies"]:
        return "# Anomalies\n\nNo anomalies.\n"
    lines = ["# Anomalies", ""]
    for anomaly in model["anomalies"]:
        lines.append(f"- {anomaly['record_type']} {anomaly['record_id']}: {anomaly['anomaly']}")
    return "\n".join(lines) + "\n"


def _png(width: int, height: int, pixels: bytearray) -> bytes:
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        start = y * stride
        raw.extend(pixels[start : start + stride])

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw)))
        + chunk(b"IEND", b"")
    )


def _fill_rect(pixels: bytearray, width: int, x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
    height = len(pixels) // (width * 3)
    x0 = max(0, min(width, x0))
    x1 = max(0, min(width, x1))
    y0 = max(0, min(height, y0))
    y1 = max(0, min(height, y1))
    for y in range(y0, y1):
        for x in range(x0, x1):
            index = (y * width + x) * 3
            pixels[index : index + 3] = bytes(color)


def render_price_chart_png(model: dict[str, Any]) -> bytes:
    width, height = 640, 360
    pixels = bytearray([248, 248, 246] * width * height)
    _fill_rect(pixels, width, 48, 40, 52, 310, (70, 70, 70))
    _fill_rect(pixels, width, 48, 306, 600, 310, (70, 70, 70))
    quotes = [quote for quote in model["quotes"] if quote.get("comparison_price") is not None]
    if not quotes:
        return _png(width, height, pixels)
    max_price = max(float(quote["comparison_price"]) for quote in quotes) or 1
    bar_width = max(24, min(80, 420 // max(1, len(quotes))))
    gap = 24
    x = 80
    for quote in quotes:
        value = float(quote["comparison_price"])
        bar_height = int((value / max_price) * 220)
        color = (48, 116, 92) if quote.get("eligible_for_lowest_price") else (165, 92, 74)
        _fill_rect(pixels, width, x, 306 - bar_height, x + bar_width, 306, color)
        x += bar_width + gap
    return _png(width, height, pixels)


def render_screenshot_fixture_png() -> bytes:
    width, height = 320, 180
    pixels = bytearray([245, 245, 242] * width * height)
    _fill_rect(pixels, width, 0, 0, width, 28, (54, 82, 96))
    _fill_rect(pixels, width, 24, 48, 140, 148, (210, 214, 208))
    _fill_rect(pixels, width, 160, 52, 290, 68, (88, 88, 88))
    _fill_rect(pixels, width, 160, 82, 245, 104, (48, 116, 92))
    _fill_rect(pixels, width, 160, 122, 280, 142, (180, 180, 174))
    return _png(width, height, pixels)
