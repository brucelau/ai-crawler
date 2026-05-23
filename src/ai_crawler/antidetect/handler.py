"""Unified block & WAF detection — one-pass analysis of HTTP responses.

Merges BlockDetector, detect_waf, extract_block_signals, and detect_block_reason
into a single BlockAnalyzer that scans the response once and returns all results.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ai_crawler.core.types import CrawlPolicy, PagePattern


class BlockType:
    NONE = "none"
    HTTP_403 = "http_403"
    HTTP_429 = "http_429"
    HTTP_451 = "http_451"
    HTTP_TIMEOUT = "http_timeout"
    CAPTCHA = "captcha"
    CLOUDFLARE = "cloudflare"
    BOT_DETECTED = "bot_detected"
    SOFT_SUSPICION = "soft_suspicion"
    EMPTY_RESPONSE = "empty_response"
    UNKNOWN = "unknown"
    IP_BLOCKED = "ip_blocked"
    HUMAN_BEHAVIOR = "human_behavior"
    INTERACTIVE_FAILED = "interactive_failed"


# ── Pattern dictionaries (merged from BlockDetector + telemetry) ──────────

_STRONG_CAPTCHA = [
    "are you a robot", "prove you're not a robot", "i am not a robot",
    "verify you are human", "complete the captcha",
    "enter the characters", "type the letters",
]

_WEAK_CAPTCHA = ["recaptcha", "hcaptcha"]

_STRONG_CF = [
    "checking your browser", "cf-challenge",
    "attention required!", "just a moment",
]

_WEAK_CF = ["cloudflare"]

_STRONG_BOT = [
    "blocked your ip", "unusual traffic",
    "automated requests", "security check failed", "robot or human?",
]

_WEAK_BOT = ["access denied", "suspicious activity", "please verify"]

_BROWSER_ERRORS = [
    "err_no_supported_proxies", "this site can't be reached",
    "this page isn't working", "this page isn’t working",
    "chrome-error://", "dns_probe_finished", "err_proxy",
    "proxy error", "sorry! something went wrong!",
    "we couldn't process your request",
    "runtime_missing_module", "cloakbrowser unavailable",
]

# Success indicators (used to short-circuit block detection)
_HARD_SUCCESS = [
    "s-item__title", "data-listingid", "ebay.com/itm/",
    "data-asin", "data-item-id", "product-title",
    '"@type":"product"', 'itemprop="price"', 'itemprop="name"',
]

_SOFT_SUCCESS = [
    "product-card", "product-tile", "data-product-id",
    "data-productid", "add to cart", "buy now",
    "search results", "results for", "price-current", "price__current",
]

_SEARCH_SUCCESS = [
    "search results", "results for", "gridcell", "product-grid",
    "product-list", "search-result", "result-item",
]

_DETAIL_SUCCESS = [
    "add to cart", "buy now", "product details",
    "about this item", "description", "specifications", 'itemprop="price"',
]

_REVIEW_SUCCESS = [
    "customer reviews", "write a review", "verified purchase",
    "out of 5 stars", "global ratings", "review this product",
]

_MIN_STRUCTURE = [
    "<html", "<body", "<main", "<div", "<script",
    'id="app"', "data-reactroot", "__next_data__", "application/ld+json",
]

# WAF signatures
_WAF_SIGNATURES: dict[str, list[str]] = {
    "incapsula": ["incapsula", "incapsula_incident_id", "_incap_", "visid_incap_"],
    "cloudflare": ["cloudflare", "cf-ray", "__cf_chl_", "cloudflare-ray"],
    "imperva": ["imperva", "incapsula", "_Incapsula_Resource", "citrix_netscaler"],
    "akamai": ["akamai", "akamai-ghost", "akamai-x-cache"],
    "aws_waf": ["aws-waf", "awswaf", "aws-waf-token"],
    "datadome": ["datadome", "datadome_cookie", "_datadome"],
    "perimeterx": ["perimeterx", "px-captcha", "_px3"],
    "f5_asm": ["f5 asm", "BIG-IP", "f5_bigip"],
    "sucuri": ["sucuri", "sucuri-cloudproxy", "_sucuri"],
    "reblaze": ["reblaze", "_rblz"],
    "fortiweb": ["fortiweb", "fortiweb-cloud"],
    "radware": ["radware"],
    "walmart": ["robot or human", "walmart.com/blocked", "walmart. save money"],
}

# Block keyword → WAF type mapping (for human-readable reasons)
_BLOCK_KEYWORD_MAP: dict[str, str] = {
    "403 forbidden": "http_403",
    "access denied": "http_403",
    "forbidden": "http_403",
    "429 too many": "http_429",
    "rate limit": "http_429",
    "too many requests": "http_429",
    "slow down": "http_429",
    "captcha": "captcha",
    "prove you're not": "captcha",
    "i am not a robot": "captcha",
    "complete the captcha": "captcha",
    "checking your browser": "cloudflare",
    "ray id": "cloudflare",
    "one more step": "cloudflare",
}

# Signal extraction — JS challenges, scripts, honeypots
_JS_CHALLENGE = [
    "eval(", "new function", "setTimeout", "document.cookie",
    "__cf_chl", "chk_jschl", "challenge-platform",
    "hcaptcha", "g-recaptcha", "turnstile",
]

_SCRIPT_SIGNALS = [
    "datadome", "perimeterx", "imperva", "incapsula",
    "cloudflare", "akamai", "shape", "fingerprint", "antibot",
]

_HONEYPOTS = [
    "display:none", "visibility:hidden", "opacity:0",
    "pointer-events:none", "overflow:hidden",
    "position:absolute", "z-index:-1", "display: none",
]

_HUMAN_BEHAVIOR = [
    "are you a robot", "prove you're not a robot",
    "i am not a robot", "verify you are human",
    "robot or human", "human verification", "confirm you're human",
]

_INTERACTIVE_FAILED = [
    "no results found", "search did not match",
    "try different keywords", "no products found", "0 results",
]

# CF subtype detection
_CF_JS = ["jschl"]
_CF_CAPTCHA = ["captcha"]
_CF_BROWSER = ["browser check"]


# ── Result dataclass ─────────────────────────────────────────────────────

@dataclass
class BlockAnalysis:
    """Unified result from a single-pass response analysis."""
    blocked: bool
    block_type: str                    # BlockType constant
    waf_type: str = ""                 # WAF vendor: cloudflare, datadome, etc.
    waf_subtype: str = ""             # js_challenge, captcha_challenge, behavioral, etc.
    captcha_type: str = ""            # recaptcha, hcaptcha, turnstile
    js_challenge: bool = False
    ip_blocked: bool = False
    human_behavior_detected: bool = False
    interactive_failed: bool = False
    is_honeypot: bool = False
    script_signals: list[str] = field(default_factory=list)
    reason: str = ""                   # human-readable block reason
    header_features: dict = field(default_factory=dict)
    latency_anomaly: str = ""
    html_size_anomaly: str = ""
    success_indicators: bool = False   # page looks like a real result


# ── Unified analyzer ─────────────────────────────────────────────────────

class BlockAnalyzer:

    @staticmethod
    def analyze(
        html: str,
        status_code: int | None,
        headers: dict | None = None,
        latency_ms: float = 0.0,
        context: BlockDetectionContext | None = None,
        use_interactive_search: bool = False,
    ) -> BlockAnalysis:
        """One-pass analysis: scan the response once, return all results.

        Replaces: BlockDetector.detect() + detect_waf() + detect_block_reason() +
                  extract_block_signals() + detect_interactive_failed()
        """
        headers = headers or {}
        html_lower = html.lower()
        html_size = len(html)
        effective_length = min(html_size, html_size)

        # ── Phase 1: HTTP status quick checks ──────────────────────────
        ip_blocked = (status_code in (403, 429) and latency_ms < 500)
        if status_code == 403:
            return BlockAnalysis(
                blocked=True, block_type=BlockType.HTTP_403,
                reason="HTTP 403 Forbidden", ip_blocked=ip_blocked,
                latency_anomaly=_latency_anomaly(latency_ms, status_code),
                html_size_anomaly=_html_size_anomaly(html_size, status_code),
                header_features=_header_features(headers, status_code, ""),
            )
        if status_code == 429:
            return BlockAnalysis(
                blocked=True, block_type=BlockType.HTTP_429,
                reason="HTTP 429 Rate Limited", ip_blocked=ip_blocked,
                latency_anomaly=_latency_anomaly(latency_ms, status_code),
                html_size_anomaly=_html_size_anomaly(html_size, status_code),
                header_features=_header_features(headers, status_code, ""),
            )
        if status_code == 451:
            return BlockAnalysis(
                blocked=True, block_type=BlockType.HTTP_451,
                reason="HTTP 451 Unavailable For Legal Reasons",
                latency_anomaly=_latency_anomaly(latency_ms, status_code),
                html_size_anomaly=_html_size_anomaly(html_size, status_code),
                header_features=_header_features(headers, status_code, ""),
            )
        if status_code is None or status_code >= 500:
            return BlockAnalysis(
                blocked=True, block_type=BlockType.HTTP_TIMEOUT,
                reason=f"HTTP {status_code or 'timeout'}",
                latency_anomaly=_latency_anomaly(latency_ms, status_code),
                html_size_anomaly=_html_size_anomaly(html_size, status_code),
                header_features=_header_features(headers, status_code, ""),
            )

        # ── Phase 2: One-pass pattern scan ─────────────────────────────
        # Strong block patterns (stop on first match)
        block_type = _match_strong_block(html_lower)
        browser_error = _has_any(html_lower, _BROWSER_ERRORS)

        # WAF detection (HTML + headers combined)
        waf_type = _detect_waf(html_lower, headers)

        # Success check
        has_hard_success = _has_any(html_lower, _HARD_SUCCESS)
        pattern = _resolve_pattern(context)
        pattern_success = _check_pattern_success(html_lower, pattern, context)

        # JS challenge
        js_challenge = _has_any(html_lower, _JS_CHALLENGE)

        # Script signals (WAF vendors in script tags)
        script_signals = [s for s in _SCRIPT_SIGNALS if s in html_lower]

        # Honeypot
        is_honeypot = _has_any(html_lower, _HONEYPOTS)

        # Header features
        header_features = _header_features(headers, status_code, waf_type)
        response_waf = waf_type  # from combined html+headers

        # CF subtype
        waf_subtype = ""
        if response_waf == "cloudflare":
            waf_subtype = _cf_subtype(html_lower, headers)
        elif response_waf == "datadome":
            waf_subtype = "behavioral_analysis"
        elif response_waf == "perimeterx":
            waf_subtype = _px_subtype(html_lower)

        # Captcha type
        captcha_type = _captcha_type(html_lower, headers)

        # Latency / size anomalies
        latency_anomaly = _latency_anomaly(latency_ms, status_code)
        html_size_anomaly = _html_size_anomaly(html_size, status_code)

        # IP blocked
        ip_blocked = (status_code in (403, 429) and latency_ms < 500)

        # Human behavior detected
        human_behavior = (_has_any(html_lower, _HUMAN_BEHAVIOR)
                          or waf_type == "datadome"
                          or waf_subtype == "behavioral_analysis"
                          or any(s in ("datadome", "perimeterx", "imperva", "shape")
                                 for s in script_signals))

        # Interactive failed
        interactive_failed = False
        if use_interactive_search and block_type == BlockType.NONE and not response_waf:
            interactive_failed = _has_any(html_lower, _INTERACTIVE_FAILED)

        # ── Phase 3: Determine block status ────────────────────────────
        if block_type:
            # Strong block signal found
            blocked = True
            reason = _build_reason(block_type, html_lower, status_code, response_waf)
        elif browser_error:
            blocked = True
            block_type = BlockType.HTTP_TIMEOUT
            reason = "Browser/proxy error detected"
        elif has_hard_success or pattern_success:
            blocked = False
            block_type = BlockType.NONE
            reason = ""
        elif _is_empty_response(status_code, html_lower, effective_length, pattern):
            blocked = True
            block_type = BlockType.EMPTY_RESPONSE
            reason = f"Empty/minimal response ({html_size} bytes)"
        elif _detect_weak_block(html_lower, effective_length, pattern):
            blocked = True
            block_type, response_waf = _resolve_weak_block(html_lower, effective_length)
            reason = _build_reason(block_type, html_lower, status_code, response_waf)
        else:
            blocked = False
            block_type = BlockType.NONE
            reason = ""

        return BlockAnalysis(
            blocked=blocked,
            block_type=block_type,
            waf_type=response_waf,
            waf_subtype=waf_subtype,
            captcha_type=captcha_type,
            js_challenge=js_challenge,
            ip_blocked=ip_blocked,
            human_behavior_detected=human_behavior,
            interactive_failed=interactive_failed,
            is_honeypot=is_honeypot,
            script_signals=script_signals,
            reason=reason,
            header_features=header_features,
            latency_anomaly=latency_anomaly,
            html_size_anomaly=html_size_anomaly,
            success_indicators=has_hard_success or pattern_success,
        )


# ── Helper functions (private) ──────────────────────────────────────────

def _has_any(text: str, patterns: list[str]) -> bool:
    return any(p in text for p in patterns)


def _match_strong_block(text: str) -> str:
    """Return block_type if a strong block pattern matches, else ''."""
    if _has_any(text, _STRONG_CF):
        return BlockType.CLOUDFLARE
    if _has_any(text, _STRONG_CAPTCHA):
        return BlockType.CAPTCHA
    if _has_any(text, _STRONG_BOT):
        return BlockType.BOT_DETECTED
    return ""


def _resolve_pattern(context: BlockDetectionContext | None) -> str:
    if context is None:
        return PagePattern.UNKNOWN.value
    if context.page_pattern and context.page_pattern != PagePattern.UNKNOWN.value:
        return context.page_pattern
    goal = (context.goal or "").lower()
    if goal == "search":
        return PagePattern.SEARCH.value
    if goal == "detail":
        return PagePattern.DETAIL.value
    if goal == "reviews":
        return PagePattern.REVIEW.value
    return PagePattern.UNKNOWN.value


def _check_pattern_success(text: str, pattern: str,
                          context: BlockDetectionContext | None = None) -> bool:
    if pattern == PagePattern.SEARCH.value and _has_any(text, _SEARCH_SUCCESS):
        return True
    if pattern == PagePattern.DETAIL.value and _has_any(text, _DETAIL_SUCCESS):
        return True
    if pattern == PagePattern.REVIEW.value and _has_any(text, _REVIEW_SUCCESS):
        return True

    if context and context.semantic_confirmation:
        sem = context.semantic_confirmation
        if sem.get("kind") == pattern and sem.get("confidence", 0) >= 0.8:
            return True
        if sem.get("entity_count", 0) >= 3 and pattern == PagePattern.SEARCH.value:
            return True

    soft_hits = sum(1 for p in _SOFT_SUCCESS if p in text)
    thresholds = {PagePattern.SEARCH.value: 2, PagePattern.DETAIL.value: 1,
                  PagePattern.REVIEW.value: 1, PagePattern.UNKNOWN.value: 2}
    required = thresholds.get(pattern, 2)
    return soft_hits >= required


def _detect_weak_block(text: str, effective_length: int, pattern: str) -> bool:
    has_structure = _has_any(text, _MIN_STRUCTURE)
    thin_thresholds = {
        PagePattern.SEARCH.value: 1200, PagePattern.DETAIL.value: 800,
        PagePattern.REVIEW.value: 700, PagePattern.UNKNOWN.value: 1500,
    }
    looks_thin = effective_length < thin_thresholds.get(pattern, 1500)
    return (_has_any(text, _WEAK_CF + _WEAK_CAPTCHA + _WEAK_BOT)
            and (looks_thin or not has_structure))


def _resolve_weak_block(text: str, effective_length: int) -> tuple[str, str]:
    if _has_any(text, _WEAK_CF):
        return BlockType.CLOUDFLARE, "cloudflare"
    if _has_any(text, _WEAK_CAPTCHA):
        return BlockType.CAPTCHA, ""
    return BlockType.BOT_DETECTED, ""


def _is_empty_response(status_code: int | None, text: str, effective_length: int,
                       pattern: str) -> bool:
    if status_code != 200:
        return False
    if "costway.com" in text:
        return False
    min_lengths = {
        PagePattern.SEARCH.value: 400, PagePattern.DETAIL.value: 220,
        PagePattern.REVIEW.value: 260, PagePattern.UNKNOWN.value: 300,
    }
    min_len = min_lengths.get(pattern, 300)
    if effective_length < 300:
        return True
    if effective_length < min_len:
        return True
    if effective_length < 5000 and not _has_any(text, _MIN_STRUCTURE):
        return True
    return False


def _detect_waf(html_lower: str, headers: dict) -> str:
    combined = html_lower + str(headers).lower()
    for waf_name, signatures in _WAF_SIGNATURES.items():
        for sig in signatures:
            if sig.lower() in combined:
                return waf_name
    return ""


def _build_reason(block_type: str, text: str, status_code: int, waf_type: str) -> str:
    reasons = []
    if status_code == 403:
        reasons.append("HTTP 403 Forbidden")
    elif status_code == 429:
        reasons.append("HTTP 429 Rate Limited")
    elif status_code and status_code >= 500:
        reasons.append(f"HTTP {status_code} Server Error")

    if waf_type == "cloudflare":
        reasons.append("Cloudflare Challenge")

    for keyword, btype in _BLOCK_KEYWORD_MAP.items():
        if keyword in text:
            if btype == "cloudflare" and "Cloudflare" not in str(reasons):
                reasons.append("Cloudflare Challenge")
            elif btype == "http_403" and "403" not in str(reasons):
                reasons.append(f"Detected: {keyword}")
            elif btype == "http_429" and "429" not in str(reasons):
                reasons.append(f"Detected: {keyword}")
            elif btype == "captcha" and "captcha" not in str(reasons):
                reasons.append(f"Captcha Challenge: {keyword}")

    if not reasons:
        if len(text) < 1000:
            reasons.append(f"Empty/Minimal Response ({len(text)} bytes)")
        else:
            reasons.append(f"Generic Block ({status_code})")

    return "; ".join(reasons)


def _latency_anomaly(latency_ms: float, status_code: int | None) -> str:
    if status_code == 200 and latency_ms > 10000:
        return "slow_page"
    if status_code in (403, 429) and latency_ms < 500:
        return "instant_reject"
    if 5000 < latency_ms < 10000:
        return "challenge_delay"
    if latency_ms < 100 and status_code == 200:
        return "suspiciously_fast"
    return ""


def _html_size_anomaly(html_size: int, status_code: int | None) -> str:
    if status_code == 200 and html_size < 500:
        return "empty_page"
    if status_code == 200 and html_size > 500000:
        return "oversized_page"
    if status_code in (403, 429) and html_size < 1000:
        return "minimal_block_page"
    if 1000 < html_size < 5000:
        return "challenge_page_size"
    return ""


def _header_features(headers: dict, status_code: int, waf_type: str) -> dict:
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


def _cf_subtype(html_lower: str, headers: dict) -> str:
    if _has_any(html_lower, _CF_JS) or _has_any(str(headers).lower(), _CF_JS):
        return "js_challenge"
    if _has_any(html_lower, _CF_CAPTCHA) or "captcha" in str(headers).lower():
        return "captcha_challenge"
    if _has_any(html_lower, _CF_BROWSER):
        return "browser_check"
    return "general_challenge"


def _px_subtype(html_lower: str) -> str:
    if "px-captcha" in html_lower:
        return "captcha"
    if "px3" in html_lower:
        return "behavioral"
    return "general"


def _captcha_type(html_lower: str, headers: dict) -> str:
    if "hcaptcha" in html_lower or "hcaptcha" in str(headers):
        return "hcaptcha"
    if "g-recaptcha" in html_lower or "recaptcha" in html_lower:
        return "recaptcha"
    if "turnstile" in html_lower:
        return "turnstile"
    return ""


# ── Context (kept for backward compat) ──────────────────────────────────

@dataclass(slots=True)
class BlockDetectionContext:
    site: str = ""
    page_pattern: str = PagePattern.UNKNOWN.value
    goal: str = ""
    semantic_confirmation: dict | None = None


# ── Legacy wrappers (backward compat) ───────────────────────────────────

class BlockDetector:
    """Legacy wrapper — delegates to BlockAnalyzer for the (blocked, block_type) API."""

    @staticmethod
    def detect(
        status_code: int | None,
        text: str,
        content_length: int,
        context: BlockDetectionContext | None = None,
    ) -> tuple[bool, str]:
        analysis = BlockAnalyzer.analyze(text, status_code, context=context)
        return analysis.blocked, analysis.block_type


class AntiBotHandler:
    def __init__(self):
        self.analyzer = BlockAnalyzer()
        self.attempt_history: dict[str, list[dict]] = {}

    def is_blocked(
        self,
        status_code: int | None,
        text: str,
        context: BlockDetectionContext | None = None,
    ) -> tuple[bool, str]:
        analysis = self.analyzer.analyze(text, status_code, context=context)
        return analysis.blocked, analysis.block_type

    def get_attempt_history(self, url: str) -> list[dict]:
        return self.attempt_history.get(url, [])

    def record_attempt(
        self, url: str, strategy: CrawlPolicy,
        block_type: str, blocked: bool,
    ) -> None:
        hist = self.attempt_history.setdefault(url, [])
        hist.append({
            "strategy": {
                "proxy": strategy.proxy.value,
                "render": strategy.render.value,
                "delay_after": strategy.delay_after,
                "use_cookies": strategy.use_cookies,
                "change_ua": strategy.change_ua,
                "use_human_scroll": strategy.use_human_scroll,
            },
            "block_type": block_type,
            "blocked": blocked,
        })
        if len(hist) > 20:
            hist[:] = hist[-20:]
