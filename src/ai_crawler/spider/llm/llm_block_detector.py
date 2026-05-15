from __future__ import annotations

import time
from typing import Optional

from ai_crawler.config import config
from ai_crawler.spider.engine.anti_bot.handler import BlockType
from ai_crawler.spider.extraction.analysis.validators import validate_block


class LLMBlockDetector:
    _instance: Optional["LLMBlockDetector"] = None
    _cache: dict[str, tuple[str, str, float]] = {}
    _cache_ttl: float = 86400.0  # 24 hours

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._dspy_detector = None

    def _get_dspy_detector(self):
        if not config.has_llm():
            return None
        if self._dspy_detector is None:
            from ai_crawler.spider.llm.dspy_model import BlockDetector

            self._dspy_detector = BlockDetector()
        return self._dspy_detector

    def _get_cache_key(self, text: str, status_code: int) -> str:
        return f"{status_code}:{hash(text[:500])}"

    def _is_cache_valid(self, cache_key: str) -> bool:
        if cache_key not in self._cache:
            return False
        _, _, cached_time = self._cache[cache_key]
        return (time.time() - cached_time) < self._cache_ttl

    def _heuristic_classify(self, status_code: int, text: str) -> tuple[str, str]:
        text_lower = text.lower()
        if status_code == 403:
            return BlockType.HTTP_403, "HTTP 403 forbidden"
        if status_code == 429:
            return BlockType.HTTP_429, "HTTP 429 rate limited"
        if status_code == 451:
            return BlockType.HTTP_451, "HTTP 451 unavailable"
        if status_code is None or status_code >= 500:
            return BlockType.HTTP_TIMEOUT, "Server error or timeout"

        if (
            "cloudflare" in text_lower
            or "cf-challenge" in text_lower
            or "checking your browser" in text_lower
        ):
            if "attention required" in text_lower or "just a moment" in text_lower:
                return BlockType.CLOUDFLARE, "Cloudflare challenge detected"
        if "captcha" in text_lower or "recaptcha" in text_lower or "hcaptcha" in text_lower:
            if "verify you are human" in text_lower or "i am not a robot" in text_lower:
                return BlockType.CAPTCHA, "CAPTCHA challenge detected"
        if "access denied" in text_lower or "blocked your ip" in text_lower:
            return BlockType.BOT_DETECTED, "Access denied"
        if "suspicious activity" in text_lower or "unusual traffic" in text_lower:
            return BlockType.BOT_DETECTED, "Suspicious activity"

        if len(text) < 500:
            return BlockType.EMPTY_RESPONSE, "Response content too short"

        return BlockType.NONE, "Normal response"

    def _classify_block(self, status_code: int, text: str, site: str) -> tuple[str, str]:
        detector = self._get_dspy_detector()
        if not detector:
            return self._heuristic_classify(status_code, text)

        try:
            raw_result = detector(site=site, status_code=status_code, response_text=text[:3000])
            result = validate_block(raw_result.__dict__)

            block_type_map = {
                "none": BlockType.NONE,
                "http_403": BlockType.HTTP_403,
                "http_429": BlockType.HTTP_429,
                "http_451": BlockType.HTTP_451,
                "http_timeout": BlockType.HTTP_TIMEOUT,
                "captcha": BlockType.CAPTCHA,
                "cloudflare": BlockType.CLOUDFLARE,
                "bot_detected": BlockType.BOT_DETECTED,
                "empty_response": BlockType.EMPTY_RESPONSE,
                "unknown": BlockType.UNKNOWN,
            }
            block_type = block_type_map.get(result.block_type, BlockType.UNKNOWN)
            return block_type, result.reasoning
        except Exception:
            return self._heuristic_classify(status_code, text)

    def detect(self, status_code: int, text: str, site: str) -> tuple[bool, str, str]:
        cache_key = self._get_cache_key(text, status_code)

        if self._is_cache_valid(cache_key):
            block_type, reasoning, _ = self._cache[cache_key]
            is_blocked = block_type != BlockType.NONE
            return is_blocked, block_type, reasoning

        block_type, reasoning = self._classify_block(status_code, text, site)
        self._cache[cache_key] = (block_type, reasoning, time.time())

        is_blocked = block_type != BlockType.NONE
        return is_blocked, block_type, reasoning


llm_block_detector = LLMBlockDetector()


def detect_block(status_code: int, text: str, site: str) -> tuple[bool, str, str]:
    return llm_block_detector.detect(status_code, text, site)
