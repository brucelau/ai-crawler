from __future__ import annotations

from scrapy import Spider

from ai_crawler.integrations.scrapy.bridge import ScrapyRuntimeBridge
from ai_crawler.spiders.base import product_to_item


class RuntimeSpider(Spider):
    name = "runtime"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 0,
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    def __init__(
        self,
        sites: str | None = None,
        query: str = "inflatable",
        pages: int = 1,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.query = query
        self.pages = int(pages)
        self.sites = [
            site.strip() for site in (sites or "amazon,walmart,target").split(",") if site.strip()
        ]
        self.runtime_bridge: ScrapyRuntimeBridge | None = None

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        spider.runtime_bridge = ScrapyRuntimeBridge(crawler.settings)
        return spider

    async def start(self):
        if self.runtime_bridge is None:
            return
        batch = self.runtime_bridge.run(self.sites, self.query, self.pages)
        for product in batch.products:
            yield product_to_item(product)
