from __future__ import annotations

from dataclasses import dataclass

from ai_crawler.spider.runtime.crawl import CrawlPolicy, PagePattern


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


@dataclass(slots=True)
class BlockDetectionContext:
    site: str = ""
    page_pattern: str = PagePattern.UNKNOWN.value
    goal: str = ""
    semantic_confirmation: dict | None = None


class BlockDetector:
    STRONG_CAPTCHA_PATTERNS = [
        "are you a robot",
        "prove you're not a robot",
        "i am not a robot",
        "verify you are human",
        "complete the captcha",
        "enter the characters",
        "type the letters",
    ]

    WEAK_CAPTCHA_PATTERNS = ["recaptcha", "hcaptcha"]

    STRONG_CF_PATTERNS = [
        "checking your browser",
        "cf-challenge",
        "attention required!",
        "just a moment",
    ]

    WEAK_CF_PATTERNS = ["cloudflare"]

    STRONG_BOT_PATTERNS = [
        "blocked your ip",
        "unusual traffic",
        "automated requests",
        "security check failed",
        "robot or human?",
    ]

    BROWSER_ERROR_PATTERNS = [
        "err_no_supported_proxies",
        "this site can't be reached",
        "this page isn’t working",
        "this page isn't working",
        "无法访问此网站",
        "网页可能暂时无法连接",
        "chrome-error://",
        "dns_probe_finished",
        "err_proxy",
        "proxy error",
        "sorry! something went wrong!",
        "we couldn't process your request",
        "runtime_missing_module",
        "cloakbrowser unavailable",
    ]

    WEAK_BOT_PATTERNS = ["access denied", "suspicious activity", "please verify"]

    HARD_SUCCESS_PATTERNS = [
        "s-item__title",
        "data-listingid",
        "ebay.com/itm/",
        "data-asin",
        "data-item-id",
        "product-title",
        '"@type":"product"',
        'itemprop="price"',
        'itemprop="name"',
    ]

    SOFT_SUCCESS_PATTERNS = [
        "product-card",
        "product-tile",
        "data-product-id",
        "data-productid",
        "add to cart",
        "buy now",
        "search results",
        "results for",
        "price-current",
        "price__current",
    ]

    MINIMUM_PAGE_STRUCTURE_PATTERNS = [
        "<html",
        "<body",
        "<main",
        "<div",
        "<script",
        'id="app"',
        "data-reactroot",
        "__next_data__",
        "application/ld+json",
    ]

    SEARCH_SUCCESS_PATTERNS = [
        "search results",
        "results for",
        "gridcell",
        "product-grid",
        "product-list",
        "search-result",
        "result-item",
    ]

    DETAIL_SUCCESS_PATTERNS = [
        "add to cart",
        "buy now",
        "product details",
        "about this item",
        "description",
        "specifications",
        'itemprop="price"',
    ]

    REVIEW_SUCCESS_PATTERNS = [
        "customer reviews",
        "write a review",
        "verified purchase",
        "out of 5 stars",
        "global ratings",
        "review this product",
    ]

    @staticmethod
    def _has_any(text: str, patterns: list[str]) -> bool:
        return any(pattern in text for pattern in patterns)

    @staticmethod
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

    def _has_success_indicators(
        self, text: str, context: BlockDetectionContext | None = None
    ) -> bool:
        if self._has_any(text, self.HARD_SUCCESS_PATTERNS):
            return True

        pattern = self._resolve_pattern(context)
        pattern_specific = []
        if pattern == PagePattern.SEARCH.value:
            pattern_specific = self.SEARCH_SUCCESS_PATTERNS
        elif pattern == PagePattern.DETAIL.value:
            pattern_specific = self.DETAIL_SUCCESS_PATTERNS
        elif pattern == PagePattern.REVIEW.value:
            pattern_specific = self.REVIEW_SUCCESS_PATTERNS

        if pattern_specific and self._has_any(text, pattern_specific):
            return True

        soft_hits = sum(1 for pattern in self.SOFT_SUCCESS_PATTERNS if pattern in text)
        if pattern == PagePattern.SEARCH.value:
            required_hits = 2
        elif pattern == PagePattern.DETAIL.value:
            required_hits = 1
        elif pattern == PagePattern.REVIEW.value:
            required_hits = 1
        else:
            required_hits = 2

        semantic = (context.semantic_confirmation or {}) if context else {}
        if semantic.get("kind") == pattern and semantic.get("confidence", 0) >= 0.8:
            return True
        if semantic.get("entity_count", 0) >= 3 and pattern == PagePattern.SEARCH.value:
            return True

        return soft_hits >= required_hits

    def _is_semantically_confirmed(self, context: BlockDetectionContext | None) -> bool:
        semantic = (context.semantic_confirmation or {}) if context else {}
        if not semantic:
            return False
        pattern = self._resolve_pattern(context)
        confidence = float(semantic.get("confidence", 0) or 0)
        entity_count = int(semantic.get("entity_count", 0) or 0)
        has_price = bool(semantic.get("has_price", False))
        has_rating = bool(semantic.get("has_rating", False))
        kind = semantic.get("kind", PagePattern.UNKNOWN.value)

        if pattern == PagePattern.SEARCH.value:
            return kind == PagePattern.SEARCH.value and confidence >= 0.65 and entity_count >= 2
        if pattern == PagePattern.DETAIL.value:
            return (
                kind == PagePattern.DETAIL.value
                and confidence >= 0.55
                and (has_price or has_rating)
            )
        if pattern == PagePattern.REVIEW.value:
            return kind == PagePattern.REVIEW.value and confidence >= 0.55 and entity_count >= 1
        return confidence >= 0.8

    def _has_minimum_page_structure(self, text: str) -> bool:
        return self._has_any(text, self.MINIMUM_PAGE_STRUCTURE_PATTERNS)

    def _detect_weak_signal_block(
        self,
        text: str,
        effective_length: int,
        context: BlockDetectionContext | None = None,
    ) -> tuple[bool, str]:
        if self._is_semantically_confirmed(context):
            return False, BlockType.NONE

        has_structure = self._has_minimum_page_structure(text)
        pattern = self._resolve_pattern(context)
        if pattern == PagePattern.SEARCH.value:
            looks_thin = effective_length < 1200
        elif pattern == PagePattern.DETAIL.value:
            looks_thin = effective_length < 800
        elif pattern == PagePattern.REVIEW.value:
            looks_thin = effective_length < 700
        else:
            looks_thin = effective_length < 1500

        if self._has_any(text, self.WEAK_CF_PATTERNS) and (looks_thin or not has_structure):
            return True, BlockType.CLOUDFLARE
        if self._has_any(text, self.WEAK_CAPTCHA_PATTERNS) and (looks_thin or not has_structure):
            return True, BlockType.CAPTCHA
        if self._has_any(text, self.WEAK_BOT_PATTERNS) and (looks_thin or not has_structure):
            return True, BlockType.BOT_DETECTED
        return False, BlockType.NONE

    def _is_empty_response(
        self,
        status_code: int | None,
        text: str,
        effective_length: int,
        context: BlockDetectionContext | None = None,
    ) -> bool:
        if status_code != 200:
            return False
        if "costway.com" in text:
            return False
        if self._has_success_indicators(text, context):
            return False
        if self._is_semantically_confirmed(context):
            return False
        pattern = self._resolve_pattern(context)
        min_lengths = {
            PagePattern.SEARCH.value: 400,
            PagePattern.DETAIL.value: 220,
            PagePattern.REVIEW.value: 260,
            PagePattern.UNKNOWN.value: 300,
        }
        min_length = min_lengths.get(pattern, 300)
        if effective_length < 300:
            return True
        if effective_length < min_length:
            return True
        if effective_length < 5000 and not self._has_minimum_page_structure(text):
            return True
        return False

    def detect(
        self,
        status_code: int | None,
        text: str,
        content_length: int,
        context: BlockDetectionContext | None = None,
    ) -> tuple[bool, str]:
        if status_code == 403:
            return True, BlockType.HTTP_403
        if status_code == 429:
            return True, BlockType.HTTP_429
        if status_code == 451:
            return True, BlockType.HTTP_451
        if status_code is None or status_code >= 500:
            return True, BlockType.HTTP_TIMEOUT

        t = text.lower()
        effective_length = min(len(text), content_length)

        for pattern in self.STRONG_CF_PATTERNS:
            if pattern in t:
                return True, BlockType.CLOUDFLARE

        for pattern in self.STRONG_CAPTCHA_PATTERNS:
            if pattern in t:
                return True, BlockType.CAPTCHA

        for pattern in self.STRONG_BOT_PATTERNS:
            if pattern in t:
                return True, BlockType.BOT_DETECTED

        for pattern in self.BROWSER_ERROR_PATTERNS:
            if pattern in t:
                return True, BlockType.HTTP_TIMEOUT

        if self._has_success_indicators(t, context):
            return False, BlockType.NONE

        weak_blocked, weak_block_type = self._detect_weak_signal_block(t, effective_length, context)
        if weak_blocked:
            return True, weak_block_type

        if self._is_empty_response(status_code, t, effective_length, context):
            return True, BlockType.EMPTY_RESPONSE

        return False, BlockType.NONE


class AntiBotHandler:
    def __init__(self):
        self.detector = BlockDetector()
        self.attempt_history: dict[str, list[dict]] = {}

    def is_blocked(
        self,
        status_code: int | None,
        text: str,
        context: BlockDetectionContext | None = None,
    ) -> tuple[bool, str]:
        content_length = len(text)
        return self.detector.detect(status_code, text, content_length, context)

    def get_attempt_history(self, url: str) -> list[dict]:
        return self.attempt_history.get(url, [])

    def record_attempt(
        self,
        url: str,
        strategy: CrawlPolicy,
        block_type: str,
        blocked: bool,
    ) -> None:
        hist = self.attempt_history.setdefault(url, [])
        hist.append(
            {
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
            }
        )
        if len(hist) > 20:
            hist[:] = hist[-20:]
