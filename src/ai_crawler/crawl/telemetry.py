"""Telemetry helpers — response header extraction and human-readable summaries.

Block detection, WAF identification, and signal extraction have moved to
antidetect.handler.BlockAnalyzer (one-pass unified analysis).
"""

from __future__ import annotations


def extract_response_headers(page, status_code: int) -> dict:
    headers = {}
    try:
        if page is not None and hasattr(page, "response"):
            headers["content_type"] = page.response.get("content-type", "")
            headers["server"] = page.response.get("server", "")
            headers["set_cookie"] = str(page.response.get("set-cookie", ""))[:200]
        elif hasattr(page, "headers"):
            headers = dict(page.headers) if page.headers else {}
    except Exception:
        pass

    if status_code in (301, 302, 303, 307, 308):
        headers["redirect"] = "Location header present"
    elif status_code == 403:
        headers["cf_challenge"] = "Challenge page suspected"
    return headers


def generate_human_summary(
    site: str,
    page_pattern: str,
    block_type: str,
    status_code: int,
    waf_detected: str,
    block_reason: str,
    tier: int,
    render_type: str,
    proxy_type: str,
    ip_rotation_count: int,
    latency_ms: float,
) -> str:
    summary_parts = [
        f"Site: {site} ({page_pattern})",
        f"Failed at Tier {tier} using {render_type} via {proxy_type}",
    ]
    if ip_rotation_count > 0:
        summary_parts.append(f"Tried {ip_rotation_count + 1} IPs before giving up")

    summary_parts.append(f"CrawlResult: {block_reason}")
    if waf_detected:
        summary_parts.append(f"WAF Detected: {waf_detected}")

    summary_parts.append(f"Response Time: {latency_ms:.0f}ms")

    if status_code:
        summary_parts.append(f"HTTP Status: {status_code}")

    return " | ".join(summary_parts)
