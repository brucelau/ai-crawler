"""Playwright downloader middleware for Scrapy."""

from __future__ import annotations

import asyncio
import random
import time

from scrapy import signals
from scrapy.http import HtmlResponse, Request, Response

from ai_crawler.browser import CamoufoxWrapper, FingerprintConfig, HumanMouseController


class PlaywrightMiddleware:
    def __init__(self):
        self._loop = None

    @classmethod
    def from_crawler(cls, crawler):
        instance = cls()
        crawler.signals.connect(instance.spider_closed, signal=signals.spider_closed)
        return instance

    def _get_loop(self):
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
        return self._loop

    def process_request(self, request: Request, spider) -> Response | Request | None:
        if not request.meta.get("render_js"):
            return None

        render_time = request.meta.get("render_wait", 2.0)
        wait_selector = request.meta.get("wait_selector")
        human_scroll = request.meta.get("human_scroll", True)
        proxy = request.meta.get("proxy")

        loop = self._get_loop()

        try:
            html = loop.run_until_complete(
                self._render(request.url, render_time, wait_selector, human_scroll, proxy)
            )
        except Exception as e:
            spider.logger.error(f"Playwright render failed: {e}")
            return None

        return HtmlResponse(
            url=request.url,
            body=html.encode("utf-8"),
            encoding="utf-8",
            request=request,
        )

    async def _render(
        self,
        url: str,
        render_time: float,
        wait_selector: str | None,
        human_scroll: bool,
        proxy: str | None,
    ) -> str:
        fp = FingerprintConfig()
        wrapper = CamoufoxWrapper(fp=fp, headless=True, proxy=proxy)

        with wrapper.stealth_page() as page:
            page.goto(url, wait_until="domcontentloaded")
            time.sleep(render_time)

            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=10000)
                except Exception:
                    pass

            if human_scroll:
                mouse = HumanMouseController(page)
                for y in range(0, 1500, random.randint(100, 200)):
                    mouse.move_to(random.randint(200, 800), y)
                    time.sleep(random.uniform(0.05, 0.15))

            return page.content()

    def process_response(self, request: Request, response: Response, spider) -> Response | Request:
        return response

    def spider_closed(self) -> None:
        if self._loop and not self._loop.is_closed():
            self._loop.close()
