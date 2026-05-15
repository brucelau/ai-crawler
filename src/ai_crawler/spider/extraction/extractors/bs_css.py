from typing import Any

from ai_crawler.spider.extraction.base import ExtractionStrategy
from ai_crawler.data.bs import get_bs_extractor
from ai_crawler.models.product import Product
from ai_crawler.config.sites import infer_site_from_url_or_empty


class BSExtractor(ExtractionStrategy):
    name = "bs_css"
    method = "beautifulsoup"

    def __init__(self):
        super().__init__(name=self.name, method=self.method)

    def extract(self, page: Any, html: str, url: str) -> list[Product]:
        source = self._infer_source(url)
        site_extractor = get_bs_extractor(source)
        if site_extractor:
            try:
                return site_extractor(html, url)
            except Exception:
                log.warning("bs_site_extraction_failed", source=source, url=url)
                return []
        return []

    def _infer_source(self, url: str) -> str:
        return infer_site_from_url_or_empty(url)


import structlog
log = structlog.get_logger()
