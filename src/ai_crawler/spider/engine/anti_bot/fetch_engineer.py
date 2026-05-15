from __future__ import annotations

import random
import time
from dataclasses import dataclass

import structlog

from ai_crawler.spider.engine.anti_bot.handler import AntiBotHandler, BlockDetectionContext, BlockType
from ai_crawler.spider.engine.anti_bot.fingerprinter import AntiBotFingerprinter
from ai_crawler.spider.engine.telemetry import (
    detect_block_reason,
    detect_waf,
    extract_block_signals,
    extract_response_headers,
)
from ai_crawler.spider.extraction import build_axtree_semantic_confirmation
from ai_crawler.spider.runtime.crawl import CrawlPolicy, CrawlTask, RenderType, PagePattern


log = structlog.get_logger()


@dataclass(slots=True)
class Attempt:
    html: str
    status_code: int | None
    page: any
    blocked: bool
    block_type: str
    latency_ms: float
    cost_estimate: float
    ip_rotation_count: int
    response_headers: dict
    waf_detected: str
    block_reason: str
    fingerprint_profile: dict
    anti_bot_fingerprint: dict
    js_challenge: bool = False
    captcha_type: str = ""


class FetchEngineer:
    UC_EARLY_ABORT_PATTERNS = [
        "err_no_supported_proxies",
        "this site can't be reached",
        "this page isn't working",
        "this page isn't working",
        "sorry! something went wrong!",
        "we couldn't process your request",
        "chrome-error://",
        "web view not found",
    ]
    SEARCH_QUALITY_MARKERS = {
        "amazon": ["data-asin", "s-search-results", "s-result-item", "a-price"],
        "target": ["/p/", "/A-", "product-card", "product-tile", 'data-test="product'],
        "ebay": ["s-item__title", "srp-results", "s-item"],
    }
    GENERIC_SEARCH_MARKERS = [
        "results for",
        "search results",
        "product-card",
        "product-grid",
        "price-current",
        "a-price",
    ]

    def __init__(
        self,
        fetcher,
        anti_bot: AntiBotHandler,
        proxy_provider,
        max_ip_retries: int,
        ip_rotation_block_types: set[str],
    ):
        self.fetcher = fetcher
        self.anti_bot = anti_bot
        self.proxy_provider = proxy_provider
        self.max_ip_retries = max_ip_retries
        self.ip_rotation_block_types = ip_rotation_block_types
        self.fingerprinter = AntiBotFingerprinter()

    def execute(self, task: CrawlTask, strategy: CrawlPolicy) -> Attempt:
        delay_min, delay_ms = strategy.delay_after
        time.sleep(random.uniform(delay_min, delay_ms))

        log.info(
            f"[CRAWL] site={task.site} url={task.url} "
            f"tier={getattr(strategy, 'tier', '?')} "
            f"render={strategy.render.value} "
            f"proxy={strategy.proxy.value} "
            f"change_ua={strategy.change_ua} "
            f"use_cookies={strategy.use_cookies} "
            f"human_scroll={strategy.use_human_scroll}"
        )

        html, status_code, page, latency_ms = self._fetch(task, strategy)
        context = self._build_detection_context(task, page)
        blocked, block_type = self.anti_bot.is_blocked(status_code, html, context)
        if (
            not blocked
            and strategy.render == RenderType.CLOUDERA
            and task.page_pattern == PagePattern.SEARCH
            and not self._has_minimum_search_quality(task, html)
        ):
            blocked, block_type = True, BlockType.EMPTY_RESPONSE
        self.anti_bot.record_attempt(task.url, strategy, block_type, blocked)

        log.info(
            f"[RESULT] site={task.site} url={task.url} "
            f"status={status_code} "
            f"blocked={blocked} "
            f"block_type={block_type.value if hasattr(block_type, 'value') else block_type} "
            f"latency_ms={latency_ms:.0f} "
            f"size={len(html)}"
        )

        ip_rotation_count = 0
        if (
            blocked
            and block_type in self.ip_rotation_block_types
            and not self.proxy_provider.disabled
            and not self._should_short_circuit_retry(task, strategy, html, block_type)
        ):
            html, status_code, page, blocked, block_type, latency_ms, ip_rotation_count = (
                self._retry_with_proxy_rotation(task, strategy, block_type)
            )

        response_headers = extract_response_headers(page, status_code or 0)
        waf_detected = detect_waf(html, response_headers) if blocked else ""
        block_reason = detect_block_reason(html, status_code or 0, waf_detected)
        fingerprint_profile = (
            self.fetcher.dynamic_profile if hasattr(self.fetcher, "dynamic_profile") else {}
        )
        anti_bot_fingerprint = self.fingerprinter.infer(
            html,
            response_headers,
            status_code,
            block_type,
            waf_detected,
            block_reason,
        ).to_dict()

        block_signals = {}
        js_challenge = False
        captcha_type = ""
        if blocked:
            block_signals = extract_block_signals(
                html=html,
                headers=response_headers,
                status_code=status_code or 0,
                latency_ms=latency_ms,
                html_size=len(html),
                waf_detected=waf_detected,
            )
            js_challenge = block_signals.js_challenge
            captcha_type = block_signals.captcha_type

        return Attempt(
            html=html,
            status_code=status_code,
            page=page,
            blocked=blocked,
            block_type=block_type,
            latency_ms=latency_ms,
            cost_estimate=self._estimate_cost(strategy, latency_ms),
            ip_rotation_count=ip_rotation_count,
            response_headers=response_headers,
            waf_detected=waf_detected,
            block_reason=block_reason,
            fingerprint_profile=fingerprint_profile,
            anti_bot_fingerprint=anti_bot_fingerprint,
            js_challenge=js_challenge,
            captcha_type=captcha_type,
        )

    def _fetch(
        self, task: CrawlTask, strategy: CrawlPolicy
    ) -> tuple[str, int | None, any, float]:
        t0 = time.time()
        html, status_code, page = self.fetcher.fetch_with_strategy(task, strategy)
        latency_ms = (time.time() - t0) * 1000
        return html, status_code, page, latency_ms

    def _retry_with_proxy_rotation(
        self,
        task: CrawlTask,
        strategy: CrawlPolicy,
        block_type: str,
    ) -> tuple[str, int | None, any, bool, str, float, int]:
        html = ""
        status_code = None
        page = None
        latency_ms = 0.0
        blocked = True
        ip_rotation_count = 0

        for ip_retry in range(self.max_ip_retries):
            log.info(
                "ip_rotation_retry",
                url=task.url,
                block_type=block_type,
                retry=ip_retry + 1,
                max_retries=self.max_ip_retries,
            )

            new_proxy = self.proxy_provider.rotate_proxy(strategy)
            if not new_proxy:
                log.warning("ip_rotation_failed_no_proxy", url=task.url)
                break

            time.sleep(random.uniform(1.0, 3.0))
            ip_rotation_count += 1

            html, status_code, page, latency_ms = self._fetch(task, strategy)
            context = self._build_detection_context(task, page)
            blocked, block_type = self.anti_bot.is_blocked(status_code, html, context)
            if not blocked:
                log.info("ip_rotation_success", url=task.url, retry=ip_retry + 1)
                break
        else:
            ip_retry = self.max_ip_retries - 1

        if blocked and ip_rotation_count and ip_retry == self.max_ip_retries - 1:
            log.warning(
                "ip_rotation_exhausted",
                url=task.url,
                block_type=block_type,
                total_retries=self.max_ip_retries,
            )

        return html, status_code, page, blocked, block_type, latency_ms, ip_rotation_count

    def _should_short_circuit_retry(
        self, task: CrawlTask, strategy: CrawlPolicy, html: str, block_type: str
    ) -> bool:
        if strategy.render.value != "cloudflare_uc":
            return False
        if block_type != "http_timeout":
            return False
        if getattr(task.page_pattern, "value", "unknown") == "search":
            return True
        lowered = html.lower()
        return any(pattern in lowered for pattern in self.UC_EARLY_ABORT_PATTERNS)

    @staticmethod
    def _estimate_cost(strategy: CrawlPolicy, latency_ms: float) -> float:
        render_cost_per_sec = 0.001
        return latency_ms / 1000 * render_cost_per_sec if strategy.render.value != "none" else 0

    @staticmethod
    def _build_detection_context(task: CrawlTask, page: any = None) -> BlockDetectionContext:
        return BlockDetectionContext(
            site=task.site,
            page_pattern=task.page_pattern.value,
            goal=str(task.metadata.get("goal", "") or ""),
            semantic_confirmation=build_axtree_semantic_confirmation(
                page, task.url, task.page_pattern.value
            )
            if page is not None
            else None,
        )

    def _has_minimum_search_quality(self, task: CrawlTask, html: str) -> bool:
        lowered = html.lower()
        site_markers = self.SEARCH_QUALITY_MARKERS.get(task.site, [])
        marker_hits = sum(1 for marker in site_markers if marker.lower() in lowered)
        if marker_hits >= 2:
            return True
        generic_hits = sum(1 for marker in self.GENERIC_SEARCH_MARKERS if marker in lowered)
        return generic_hits >= 2
