"""Target site adapter — search via redsky_aggregations API.

Product data is loaded from the redsky API. The engine fetches the API
response through the proxy and passes it to extract_api().
"""

from __future__ import annotations

import uuid

from ai_crawler.core.types import Product
from ai_crawler.sites.registry import Command, register

_REDSKY_URL = "https://redsky.target.com/redsky_aggregations/v1/web/plp_search_v2"
_API_KEY = "9f36aeafbe60771e321a7cc95a78140772ab3e96"


@register(site="target", command="search")
class TargetSearch(Command):
    site = "target"
    command = "search"
    url_template = "https://www.target.com/s?searchTerm={query}"
    api_url_template = _REDSKY_URL

    start_level = 0

    def build_url(self, query: str, page: int = 1) -> str:
        from urllib.parse import quote_plus
        return self.url_template.format(query=quote_plus(query))

    def build_api_params(self, query: str) -> dict:
        return {
            "key": _API_KEY,
            "keyword": query,
            "count": "24",
            "offset": "0",
            "default_purchasable_filter": "false",
            "channel": "WEB",
            "page": f"/s/{query}",
            "pricing_store_id": "3991",
            "visitor_id": str(uuid.uuid4()),
            "has_size_context": "false",
        }

    def extract(self, html: str, url: str) -> list[Product]:
        from ai_crawler.sites.target.bs import extract as bs_extract
        return bs_extract(html, url)

    def extract_api(self, data: dict) -> list[Product]:
        return _parse_products(data)


def _parse_products(data: dict) -> list[Product]:
    products_data = data.get("data", {}).get("search", {}).get("products", [])
    results: list[Product] = []
    seen: set[str] = set()

    for p in products_data:
        item = p.get("item", {})
        description = item.get("product_description", {})
        enrichment = item.get("enrichment", {})
        price_info = p.get("price", {})
        image_info = enrichment.get("image_info", {})
        brand = item.get("primary_brand", {})
        ratings = p.get("ratings_and_reviews", {}).get("statistics", {}).get("rating", {})

        title = description.get("title", "")
        buy_url = enrichment.get("buy_url", "")
        tcin = p.get("tcin", "")

        if not title or not buy_url:
            continue

        if tcin in seen:
            continue
        seen.add(tcin)

        if "?" in buy_url:
            buy_url = buy_url.split("?")[0]

        primary = image_info.get("primary_image", {})
        image_url = primary.get("url", "")
        alt_images = [
            img.get("url", "")
            for img in image_info.get("alternate_images", [])
            if img.get("url")
        ]

        price = _normalize_price(price_info.get("formatted_current_price", ""))
        reg_price = _normalize_price(price_info.get("formatted_comparison_price", ""))

        description_text = ""
        if price_info.get("save_percent"):
            description_text = f'Save {price_info["save_percent"]}%'

        rating_avg = ratings.get("average")
        rating_text = str(rating_avg) if rating_avg else ""

        prod = Product(
            source="target",
            url=buy_url,
            title=title[:200],
            price=price,
            images=[image_url] + alt_images if image_url else alt_images,
            rating=rating_text,
            brand=brand.get("name", ""),
        )
        if reg_price and reg_price != price:
            prod.description = description_text or f"Was {price_info.get('formatted_comparison_price', '')}"
        elif description_text:
            prod.description = description_text
        results.append(prod)

    return results


def _normalize_price(text: str) -> str:
    import re
    m = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
    return m.group() if m else ""
