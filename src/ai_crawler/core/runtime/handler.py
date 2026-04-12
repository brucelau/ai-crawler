from __future__ import annotations

from ai_crawler.core.strategy import CrawlStrategy, ProxyType, RenderType


class BlockType:
    NONE = "none"
    HTTP_403 = "http_403"
    HTTP_429 = "http_429"
    HTTP_451 = "http_451"
    HTTP_TIMEOUT = "http_timeout"
    CAPTCHA = "captcha"
    CLOUDFLARE = "cloudflare"
    BOT_DETECTED = "bot_detected"
    EMPTY_RESPONSE = "empty_response"
    UNKNOWN = "unknown"


class BlockDetector:
    # Patterns that indicate real captcha challenge (not just the word in config/metadata)
    CAPTCHA_PATTERNS = [
        "are you a robot",
        "prove you're not a robot",
        "i am not a robot",
        "verify you are human",
        "complete the captcha",
        "enter the characters",
        "type the letters",
        "recaptcha",
        "hcaptcha",
        "cf-challenge",
        "checking your browser",
    ]

    # Patterns for Cloudflare challenge pages
    CF_PATTERNS = [
        "cloudflare",
        "checking your browser",
        "cf-challenge",
        "attention required!",
        "just a moment",
    ]

    # Patterns for actual bot detection / access denied (not meta tags)
    BOT_PATTERNS = [
        "access denied",
        "blocked your ip",
        "suspicious activity",
        "unusual traffic",
        "automated requests",
        "please verify",
        "security check failed",
    ]

    def detect(self, status_code: int | None, text: str, content_length: int) -> tuple[bool, str]:
        if status_code == 403:
            return True, BlockType.HTTP_403
        if status_code == 429:
            return True, BlockType.HTTP_429
        if status_code == 451:
            return True, BlockType.HTTP_451
        if status_code is None or status_code >= 500:
            return True, BlockType.HTTP_TIMEOUT

        t = text.lower()

        if "s-item__title" in t or "data-listingid" in t or "ebay.com/itm/" in t:
            return False, BlockType.NONE

        if "data-asin" in t or "data-item-id" in t or "product-title" in t:
            return False, BlockType.NONE

        for pattern in self.CF_PATTERNS:
            if pattern in t:
                return True, BlockType.CLOUDFLARE

        for pattern in self.CAPTCHA_PATTERNS:
            if pattern in t:
                if len(text) > 100000 and pattern in ["recaptcha", "hcaptcha", "cloudflare"]:
                    continue
                return True, BlockType.CAPTCHA

        for pattern in self.BOT_PATTERNS:
            if pattern in t:
                return True, BlockType.BOT_DETECTED

        if len(text) < 1000 or content_length < 5000:
            if status_code == 200 and "costway.com" in t:
                return False, BlockType.NONE
            return True, BlockType.EMPTY_RESPONSE

        return False, BlockType.NONE

        # Amazon/Walmart success indicators
        if "data-asin" in t or "data-item-id" in t or "product-title" in t:
            return False, BlockType.NONE

        for pattern in self.CF_PATTERNS:
            if pattern in t:
                return True, BlockType.CLOUDFLARE

        for pattern in self.CAPTCHA_PATTERNS:
            if pattern in t:
                # If page is huge, a single word might be a false positive
                if len(text) > 100000 and pattern in ["recaptcha", "hcaptcha", "cloudflare"]:
                    continue
                return True, BlockType.CAPTCHA

        for pattern in self.BOT_PATTERNS:
            if pattern in t:
                return True, BlockType.BOT_DETECTED

        if len(text) < 1000 or content_length < 5000:
            if status_code == 200 and "costway.com" in t:
                return False, BlockType.NONE
            return True, BlockType.EMPTY_RESPONSE

        return False, BlockType.NONE


class AntiBotHandler:
    def __init__(self):
        self.detector = BlockDetector()
        self.attempt_history: dict[str, list[dict]] = {}

    def is_blocked(self, status_code: int | None, text: str) -> tuple[bool, str]:
        content_length = len(text)
        return self.detector.detect(status_code, text, content_length)

    def get_attempt_history(self, url: str) -> list[dict]:
        return self.attempt_history.get(url, [])

    def record_attempt(
        self,
        url: str,
        strategy: CrawlStrategy,
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
