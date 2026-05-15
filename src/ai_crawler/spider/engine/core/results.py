from __future__ import annotations

from dataclasses import dataclass

from ai_crawler.spider.engine.anti_bot.handler import BlockType
from ai_crawler.spider.runtime.crawl import CrawlPolicy, CrawlTask
from ai_crawler.models.product import Product


@dataclass
class CrawlResult:
    task: CrawlTask
    strategy: CrawlPolicy
    success: bool
    html: str = ""
    products: list[Product] = None
    block_type: str = BlockType.NONE
    error: str = ""
    extraction_strategy: str = "none"
    extraction_method: str = "none"
    extraction_metadata: dict | None = None
    anti_bot_fingerprint: dict | None = None
