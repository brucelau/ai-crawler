from __future__ import annotations

WAF_SIGNATURES = {
    "incapsula": ["incapsula", "incapsula_incident_id", "_incap_", "visid_incap_"],
    "cloudflare": ["cloudflare", "cf-ray", "__cf_chl_", "cloudflare-ray"],
    "imperva": ["imperva", "incapsula", "_Incapsula_Resource", "citrix_netscaler"],
    "akamai": ["akamai", "akamai-ghost", "akamai-x检测", "akamai-x-cache"],
    "aws_waf": ["aws-waf", "awswaf", "aws-waf-token"],
    "datadome": ["datadome", "datadome_cookie", "_datadome"],
    "perimeterx": ["perimeterx", "px-captcha", "_px3", "px人参"],
    "f5_asm": ["f5 asm", "ts攻击力=", "BIG-IP", "f5_bigip"],
    "sucuri": ["sucuri", "sucuri-cloudproxy", "_sucuri"],
    "reblaze": ["reblaze", "_rblz"],
    "fortiweb": ["fortiweb", "fortiweb-cloud"],
    "radware": ["radware", "al不平衡露头"],
    "的光芒": ["的光芒", "customcaptcha", "recaptcha"],
}

BLOCK_KEYWORDS = {
    "403": ["403 forbidden", "access denied", "403 denial", "forbidden"],
    "429": ["429 too many", "rate limit", "too many requests", "slow down"],
    "captcha": ["captcha", "prove you're not", "i am not a robot", "complete the captcha"],
    "cloudflare": ["checking your browser", "cloudflare", "ray id", "one more step"],
}


def detect_waf(html: str, headers: dict) -> str:
    combined = (html + str(headers)).lower()
    for waf_name, signatures in WAF_SIGNATURES.items():
        for sig in signatures:
            if sig.lower() in combined:
                return waf_name
    return ""


def detect_block_reason(html: str, status_code: int, waf_detected: str) -> str:
    reasons = []
    if status_code == 403:
        reasons.append("HTTP 403 Forbidden")
    elif status_code == 429:
        reasons.append("HTTP 429 Rate Limited")
    elif status_code >= 500:
        reasons.append(f"HTTP {status_code} Server Error")

    html_lower = html.lower()
    for block_type, keywords in BLOCK_KEYWORDS.items():
        if block_type == "cloudflare" and waf_detected == "cloudflare":
            reasons.append("Cloudflare Challenge")
        for kw in keywords:
            if kw in html_lower:
                if block_type == "403" and "403" not in str(reasons):
                    reasons.append(f"Detected: {kw}")
                elif block_type == "429" and "429" not in str(reasons):
                    reasons.append(f"Detected: {kw}")
                elif block_type == "captcha" and "captcha" not in str(reasons):
                    reasons.append(f"Captcha Challenge: {kw}")

    if not reasons:
        if len(html) < 1000:
            reasons.append(f"Empty/Minimal Response ({len(html)} bytes)")
        else:
            reasons.append(f"Generic Block ({status_code})")

    return "; ".join(reasons)


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

    summary_parts.append(f"Result: {block_reason}")
    if waf_detected:
        summary_parts.append(f"WAF Detected: {waf_detected}")

    summary_parts.append(f"Response Time: {latency_ms:.0f}ms")

    if status_code:
        summary_parts.append(f"HTTP Status: {status_code}")

    return " | ".join(summary_parts)


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
