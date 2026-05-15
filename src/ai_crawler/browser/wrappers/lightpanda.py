"""LightpandaWrapper - Tier 3: Lightpanda lightweight browser for sub-100ms JS rendering."""

import subprocess
import time
from typing import Generator

from ai_crawler.browser.base import BaseWrapper


class LightpandaWrapper(BaseWrapper):
    def __init__(
        self,
        proxy: str | None = None,
        headless: bool = True,
        wait_time: float = 2.0,
        human_scroll: bool = True,
        dynamic_profile: dict | None = None,
    ):
        self.proxy = proxy
        self.headless = headless
        self.wait_time = wait_time
        self.human_scroll = human_scroll
        self.dynamic_profile = dynamic_profile or {}
        self._process: subprocess.Popen | None = None
        self._cdp_url: str | None = None

    def launch(self) -> Generator["LightpandaWrapper", None, None]:
        try:
            self._start_lightpanda()
            yield self
        finally:
            self._stop_lightpanda()

    def _start_lightpanda(self) -> None:
        cmd = ["lightpanda", "run", "--headless"]
        if self.proxy:
            cmd.extend(["--proxy", self.proxy])
        self._process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self._cdp_url = "http://localhost:9222"
        time.sleep(2)

    def _stop_lightpanda(self) -> None:
        if self._process:
            self._process.terminate()
            self._process.wait(timeout=5)
            self._process = None
        self._cdp_url = None

    def fetch(self, url: str) -> tuple[str, int]:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(self._cdp_url)
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(self.wait_time)
                html = page.content()
                status = 200
                page.close()
                browser.close()
            return html, status
        except Exception as e:
            raise e

    def _human_scroll(self, page) -> None:
        if not self.human_scroll:
            return
        from random import randint, uniform

        for _ in range(randint(2, 5)):
            page.evaluate(f"window.scrollBy(0, {randint(200, 500)})")
            time.sleep(uniform(0.5, 1.5))

    def __repr__(self) -> str:
        return f"LightpandaWrapper(proxy={self.proxy}, cdp={self._cdp_url})"
