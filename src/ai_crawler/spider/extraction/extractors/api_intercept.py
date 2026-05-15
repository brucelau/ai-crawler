import structlog
from typing import Any

from ai_crawler.spider.extraction.base import ExtractionStrategy
from ai_crawler.models.product import Product

log = structlog.get_logger()


class APIInterceptExtractor(ExtractionStrategy):
    def __init__(self, name: str, method: str):
        super().__init__(name, method)
        self._captured_responses: list[dict] = []

    def extract(self, page: Any, html: str, url: str) -> list[Product]:
        return []

    def intercept(self, response: Any) -> None:
        try:
            content_type = response.headers.get("content-type", "")
            if "json" in content_type and self._is_product_api(response.url):
                data = response.json()
                if data:
                    self._captured_responses.append(data)
        except Exception:
            log.debug("api_intercept_failed", url=response.url)

    def get_and_clear(self) -> list[Product]:
        products = self._parse_responses(self._captured_responses)
        self._captured_responses = []
        return products

    def _is_product_api(self, url: str) -> bool:
        return any(k in url.lower() for k in ["product", "search", "item", "listing"])

    def _parse_responses(self, responses: list[dict]) -> list[Product]:
        products = []
        for resp in responses:
            items = self._find_products(resp)
            products.extend(items)
        return products

    def _find_products(self, data: Any) -> list[Product]:
        if isinstance(data, dict):
            if "products" in data:
                return self._find_products(data["products"])
            if "items" in data:
                return self._find_products(data["items"])
            if "results" in data:
                return self._find_products(data["results"])
            if data.get("@type") == "Product":
                return [self._dict_to_product(data)]
        if isinstance(data, list):
            results = []
            for item in data:
                results.extend(self._find_products(item))
            return results
        return []

    def _dict_to_product(self, item: dict) -> Product:
        offers = item.get("offers", {}) or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = str(offers.get("price", "")) if offers else ""
        return Product(
            source="unknown",
            url=item.get("url", ""),
            title=item.get("name", ""),
            price=price,
            images=[item.get("image", "")] if item.get("image") else [],
        )
