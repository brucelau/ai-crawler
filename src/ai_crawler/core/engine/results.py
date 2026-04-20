from __future__ import annotations

from dataclasses import dataclass

from ai_crawler.core.engine.handler import BlockType
from ai_crawler.core.strategy import CrawlStrategy, CrawlTask
from ai_crawler.models.product import Product


@dataclass
class CrawlResult:
    task: CrawlTask
    strategy: CrawlStrategy
    success: bool
    html: str = ""
    products: list[Product] = None
    block_type: str = BlockType.NONE
    error: str = ""
    extraction_strategy: str = "none"
    extraction_method: str = "none"
    extraction_metadata: dict | None = None
    anti_bot_fingerprint: dict | None = None
