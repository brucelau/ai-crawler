import json
from typing import Any

from bs4 import BeautifulSoup

from ai_crawler.core.extraction.base import ExtractionResult, ExtractionStrategy
from ai_crawler.models.product import Product
from ai_crawler.utils.site import infer_site_from_url


class JSONLDExtraction(ExtractionStrategy):
    name = "json_ld"
    method = "beautifulsoup"

    def extract(self, page: Any, html: str, url: str) -> list[Product]:
        soup = BeautifulSoup(html, "html.parser")
        products = []
        seen = set()

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") == "Product":
                        name = item.get("name", "")
                        if not name or name in seen:
                            continue
                        seen.add(name)

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

                        products.append(
                            Product(
                                source=infer_site_from_url(url),
                                url=url,
                                title=name,
                                price=price,
                                brand=brand,
                                images=[image] if image else [],
                            )
                        )
            except (json.JSONDecodeError, TypeError, KeyError):
                continue

        return products
