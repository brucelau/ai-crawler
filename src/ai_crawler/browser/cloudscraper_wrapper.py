"""CloudScraperWrapper - Tier 2: cloudscraper for simple anti-bot bypass."""

import cloudscraper

from ai_crawler.browser.base import BaseWrapper


class CloudScraperWrapper(BaseWrapper):
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
            scraper = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "desktop": True},
                proxy=self.proxy,
            )
            resp = scraper.get(url, timeout=30)
            return resp.text, resp.status_code
        except Exception as e:
            raise e

    def __repr__(self) -> str:
        return f"CloudScraperWrapper(proxy={self.proxy})"
