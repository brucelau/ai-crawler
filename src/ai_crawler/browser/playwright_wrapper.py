"""PlaywrightWrapper - Tier 3: full JavaScript rendering with Playwright."""

import random
import time

from playwright.sync_api import sync_playwright

from ai_crawler.browser.base import BaseWrapper


class PlaywrightWrapper(BaseWrapper):
    def __init__(
        self,
        proxy: str | None = None,
        headless: bool = True,
        wait_time: float = 2.0,
        human_scroll: bool = False,
        dynamic_profile: dict | None = None,
    ):
        self.proxy = proxy
        self.headless = headless
        self.wait_time = wait_time
        self.human_scroll = human_scroll
        self.dynamic_profile = dynamic_profile or {}

    def fetch(self, url: str) -> tuple[str, int]:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context(
                    proxy={"server": self.proxy} if self.proxy else None,
                    ignore_https_errors=True,
                )
                page = context.new_page()
                page.goto(url, timeout=30000)
                page.wait_for_load_state("networkidle")

                if self.wait_time > 0:
                    time.sleep(self.wait_time)

                if self.human_scroll:
                    self._human_scroll(page)

                html = page.content()
                browser.close()
                return html, 200
        except Exception as e:
            return f"error: {e}", 0

    def _human_scroll(self, page):
        for _ in range(random.randint(2, 5)):
            page.evaluate(f"window.scrollBy(0, {random.randint(200, 500)})")
            time.sleep(random.uniform(0.5, 1.5))

    def __repr__(self) -> str:
        return f"PlaywrightWrapper(proxy={self.proxy}, headless={self.headless})"
