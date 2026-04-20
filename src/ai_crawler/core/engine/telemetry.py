from __future__ import annotations
from dataclasses import dataclass, field

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

JS_CHALLENGE_PATTERNS = [
    "eval(",
    "new Function",
    "setTimeout",
    "document.cookie",
    "__cf_chl",
    "chk_jschl",
    "cf验证码",
    "challenge-platform",
    "hcaptcha",
    "g-recaptcha",
    "turnstile",
]

SCRIPT_PATTERNS = [
    "datadome",
    "perimeterx",
    "imperva",
    "incapsula",
    "cloudflare",
    "akamai",
    "shape",
    "fingerprint",
    "antibot",
]

HONEYPOT_PATTERNS = [
    "display:none",
    "visibility:hidden",
    "opacity:0",
    "pointer-events:none",
    "overflow:hidden",
    "position:absolute",
    "z-index:-1",
    "display: none",
]


@dataclass
class BlockSignals:
    waf_type: str = ""
    waf_subtype: str = ""
    js_challenge: bool = False
    captcha_type: str = ""
    script_signals: list[str] = field(default_factory=list)
    is_honeypot: bool = False
    latency_anomaly: str = ""
    header_features: dict = field(default_factory=dict)
    html_size_anomaly: str = ""
    ip_blocked: bool = False
    human_behavior_detected: bool = False
    interactive_failed: bool = False


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


def extract_block_signals(
    html: str,
    headers: dict,
    status_code: int,
    latency_ms: float,
    html_size: int,
    waf_detected: str = "",
) -> BlockSignals:
    signals = BlockSignals(waf_type=waf_detected)
    html_lower = html.lower()

    for js_pattern in JS_CHALLENGE_PATTERNS:
        if js_pattern.lower() in html_lower:
            signals.js_challenge = True
            break

    for script_sig in SCRIPT_PATTERNS:
        if script_sig.lower() in html_lower:
            signals.script_signals.append(script_sig)

    for honeypot in HONEYPOT_PATTERNS:
        if honeypot in html_lower:
            signals.is_honeypot = True
            break

    signals.latency_anomaly = _detect_latency_anomaly(latency_ms, status_code)
    signals.html_size_anomaly = _detect_html_size_anomaly(html_size, status_code)

    signals.header_features = _extract_header_features(headers, status_code, waf_detected)

    if signals.waf_type == "cloudflare":
        signals.waf_subtype = _detect_cloudflare_subtype(html_lower, headers)
    elif signals.waf_type == "datadome":
        signals.waf_subtype = "behavioral_analysis"
    elif signals.waf_type == "perimeterx":
        signals.waf_subtype = _detect_perimeterx_subtype(html_lower)

    if "hcaptcha" in html_lower or "hcaptcha" in str(headers):
        signals.captcha_type = "hcaptcha"
    elif "g-recaptcha" in html_lower or "recaptcha" in html_lower:
        signals.captcha_type = "recaptcha"
    elif "turnstile" in html_lower:
        signals.captcha_type = "turnstile"

    signals.ip_blocked = detect_ip_blocked(status_code, latency_ms, signals.latency_anomaly)
    signals.human_behavior_detected = detect_human_behavior_failure(
        html_lower, signals.waf_subtype, signals.waf_type, signals.script_signals
    )

    return signals


def _detect_latency_anomaly(latency_ms: float, status_code: int) -> str:
    if status_code == 200 and latency_ms > 10000:
        return "slow_page"
    if status_code in (403, 429) and latency_ms < 500:
        return "instant_reject"
    if 5000 < latency_ms < 10000:
        return "challenge_delay"
    if latency_ms < 100 and status_code == 200:
        return "suspiciously_fast"
    return ""


def _detect_html_size_anomaly(html_size: int, status_code: int) -> str:
    if status_code == 200 and html_size < 500:
        return "empty_page"
    if status_code == 200 and html_size > 500000:
        return "oversized_page"
    if status_code in (403, 429) and html_size < 1000:
        return "minimal_block_page"
    if 1000 < html_size < 5000:
        return "challenge_page_size"
    return ""


def _extract_header_features(headers: dict, status_code: int, waf_type: str) -> dict:
    features = {}
    headers_lower = {k.lower(): str(v).lower() for k, v in headers.items()}

    if "cf-ray" in headers_lower or "cf-ray" in str(headers):
        features["cf_ray"] = True
        features["cf_datacenter"] = headers.get("cf-ray", "").split("-")[-1] if headers.get("cf-ray") else ""

    if "x-datadome" in headers_lower:
        features["x_datadome"] = headers.get("x-datadome", "")[:50]

    if "server" in headers_lower:
        features["server_type"] = headers["server"]

    if "set-cookie" in headers_lower:
        features["sets_cookie"] = True

    if "x-request-id" in headers_lower or "x-correlation-id" in headers_lower:
        features["has_correlation_id"] = True

    if waf_type == "cloudflare":
        if "cf-cache-status" in headers_lower:
            features["cf_cache_status"] = headers["cf-cache-status"]
        if "cf-request-id" in headers_lower:
            features["cf_request_id"] = True

    return features


def _detect_cloudflare_subtype(html_lower: str, headers: dict) -> str:
    if "jschl" in html_lower or "jschl" in str(headers):
        return "js_challenge"
    if "captcha" in html_lower or " CAPTCHA" in str(headers):
        return "captcha_challenge"
    if "browser check" in html_lower:
        return "browser_check"
    return "general_challenge"


def _detect_perimeterx_subtype(html_lower: str) -> str:
    if "px-captcha" in html_lower:
        return "captcha"
    if "px3" in html_lower:
        return "behavioral"
    return "general"


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


HUMAN_BEHAVIOR_PATTERNS = [
    "are you a robot",
    "prove you're not a robot",
    "i am not a robot",
    "verify you are human",
    "robot or human",
    "human verification",
    "confirm you're human",
]

INTERACTIVE_FAILED_PATTERNS = [
    "no results found",
    "search did not match",
    "try different keywords",
    "no products found",
    "0 results",
]


def detect_ip_blocked(status_code: int, latency_ms: float, waf_subtype: str) -> bool:
    if status_code in (403, 429) and latency_ms < 500:
        return True
    if status_code == 403 and waf_subtype == "instant_reject":
        return True
    return False


def detect_human_behavior_failure(
    html: str,
    waf_subtype: str,
    waf_type: str,
    script_signals: list[str],
) -> bool:
    if waf_type == "datadome":
        return True
    if waf_subtype == "behavioral_analysis":
        return True
    html_lower = html.lower()
    for pattern in HUMAN_BEHAVIOR_PATTERNS:
        if pattern in html_lower:
            return True
    behavioral_signals = ["datadome", "perimeterx", "imperva", "shape"]
    for signal in script_signals:
        if signal.lower() in behavioral_signals:
            return True
    return False


def detect_interactive_failed(
    html: str,
    block_type: str,
    waf_type: str,
    use_interactive_search: bool,
) -> bool:
    if not use_interactive_search:
        return False
    if block_type == "none" and waf_type == "":
        html_lower = html.lower()
        for pattern in INTERACTIVE_FAILED_PATTERNS:
            if pattern in html_lower:
                return True
    return False
