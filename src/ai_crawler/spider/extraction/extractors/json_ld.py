import json
from typing import Any

from bs4 import BeautifulSoup

from ai_crawler.spider.extraction.base import ExtractionResult, ExtractionStrategy
from ai_crawler.models.product import Product
from ai_crawler.config.sites import infer_site_from_url


class JSONLDExtractor(ExtractionStrategy):
    name = "json_ld"
    method = "beautifulsoup"

    def __init__(self):
        super().__init__(name=self.name, method=self.method)

    def extract(self, page: Any, html: str, url: str) -> list[Product]:
        soup = BeautifulSoup(html, "html.parser")
        products = []
        seen = set()

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    self._extract_products_from_item(item, url, seen, products)
            except (json.JSONDecodeError, TypeError, KeyError):
                continue

        return products

    def _extract_products_from_item(self, item: dict, url: str, seen: set, products: list) -> None:
        if not isinstance(item, dict):
            return

        if item.get("@type") == "Product":
            product = self._parse_product(item, url)
            if product and product.title not in seen:
                seen.add(product.title)
                products.append(product)
            return

        for key, value in item.items():
            if key in ("mainEntity", "itemOffered", "offers"):
                if isinstance(value, dict):
                    self._extract_products_from_item(value, url, seen, products)
                elif isinstance(value, list):
                    for v in value:
                        self._extract_products_from_item(v, url, seen, products)

    def _parse_product(self, item: dict, url: str) -> Product | None:
        name = item.get("name", "")
        if not name:
            return None

        offers = item.get("offers", {}) or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}

        price = ""
        if offers:
            price = str(offers.get("price", ""))
            price_currency = offers.get("priceCurrency", "")
            if price and price_currency:
                price = f"{price_currency} {price}"

        brand = ""
        brand_data = item.get("brand")
        if isinstance(brand_data, str):
            brand = brand_data
        elif isinstance(brand_data, dict):
            brand = brand_data.get("name", "")

        image = ""
        img = item.get("image")
        if isinstance(img, str):
            image = img
        elif isinstance(img, list) and img:
            image = img[0]

        return Product(
            source=infer_site_from_url(url),
            url=url,
            title=name,
            price=price,
            brand=brand,
            images=[image] if image else [],
        )
