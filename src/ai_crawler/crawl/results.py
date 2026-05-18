from __future__ import annotations

from dataclasses import dataclass, field

from ai_crawler.antidetect.handler import BlockType
from ai_crawler.core.types import CrawlPolicy, CrawlTask
from ai_crawler.core.types import Product


@dataclass
class CrawlResult:
    task: CrawlTask
    strategy: CrawlPolicy
    success: bool
    html: str = ""
    products: list[Product] = field(default_factory=list)
    block_type: str = BlockType.NONE
    error: str = ""
    extraction_strategy: str = "none"
    extraction_method: str = "none"
    extraction_metadata: dict | None = None
    anti_bot_fingerprint: dict | None = None
