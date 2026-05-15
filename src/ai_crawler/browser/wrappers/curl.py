"""CurlWrapper - Tier 1: simple HTTP requests without JavaScript rendering."""

import requests

from ai_crawler.browser.base import BaseWrapper


class CurlWrapper(BaseWrapper):
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
            resp = requests.get(
                url,
                proxy=self.proxy,
                timeout=30,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                },
            )
            return resp.text, resp.status_code
        except Exception as e:
            return f"error: {e}", 0

    def __repr__(self) -> str:
        return f"CurlWrapper(proxy={self.proxy})"
