import structlog
from typing import Any

from ai_crawler.core.extraction.base import ExtractionResult, ExtractionStrategy
from ai_crawler.core.extraction.site_configs import get_js_code
from ai_crawler.models.product import Product
from ai_crawler.utils.site import infer_site_from_url

log = structlog.get_logger()


class JSEvaluateExtraction(ExtractionStrategy):
    name = "js_eval"
    method = "page_evaluate"

    def __init__(self):
        super().__init__(name=self.name, method=self.method)

    def extract(self, page: Any, html: str, url: str) -> list[Product]:
        if page is None:
            return []

        source = self._infer_source(url)

        js_code = self._get_js_code(source)
        if not js_code:
            return []

        try:
            items = page.evaluate(js_code)
            if not isinstance(items, list):
                return []
            products: list[Product] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title", "") or "").strip()
                if not title:
                    continue
                products.append(
                    Product(
                        source=source,
                        url=str(item.get("url", url) or url),
                        title=title,
                        price=str(item.get("price", "") or "").strip(),
                        rating=float(item.get("rating", 0) or 0),
                        review_count=int(item.get("review_count", 0) or 0),
                        images=[item.get("image")] if item.get("image") else [],
                        asin=str(item.get("asin", "") or "").strip(),
                    )
                )
            return products
        except Exception:
            log.warning("js_evaluation_extraction_failed", url=url)
            return []

    def _infer_source(self, url: str) -> str:
        return infer_site_from_url(url)

    def _get_js_code(self, source: str) -> str | None:
        return get_js_code(source)
