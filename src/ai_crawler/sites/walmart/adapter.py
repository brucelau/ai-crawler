"""Walmart site adapter — extracts from __NEXT_DATA__ SSR JSON."""

from __future__ import annotations

import json
from bs4 import BeautifulSoup

from ai_crawler.core.types import Product
from ai_crawler.sites.registry import Command, register


@register(site="walmart", command="search")
class WalmartSearch(Command):
    site = "walmart"
    command = "search"
    url_template = "https://www.walmart.com/search?q={query}"

    start_level = 0

    def build_url(self, query: str, page: int = 1) -> str:
        from urllib.parse import quote_plus
        url = self.url_template.format(query=quote_plus(query))
        if page > 1:
            url += f"&page={page}"
        return url

    def extract(self, html: str, url: str) -> list[Product]:
        return _parse_next_data(html)


def _parse_next_data(html: str) -> list[Product]:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script:
        return []

    try:
        data = json.loads(script.text)
    except json.JSONDecodeError:
        return []

    search_result = (
        data.get("props", {})
        .get("pageProps", {})
        .get("initialData", {})
        .get("searchResult", {})
    )
    item_stacks = search_result.get("itemStacks", [])
    if not item_stacks:
        return []

    items = item_stacks[0].get("items", [])
    products: list[Product] = []
    seen: set[str] = set()

    for item in items:
        us_item_id = item.get("usItemId", "")
        if not us_item_id or us_item_id in seen:
            continue
        seen.add(us_item_id)

        name = item.get("name", "")
        if not name:
            continue

        canonical = item.get("canonicalUrl", "")
        product_url = f"https://www.walmart.com{canonical}" if canonical else ""

        price = ""
        price_info = item.get("priceInfo", {})
        line_price = price_info.get("linePrice", "")
        if line_price:
            price = line_price.replace("$", "")

        image = ""
        image_info = item.get("imageInfo", {})
        if image_info.get("thumbnailUrl"):
            image = image_info["thumbnailUrl"]

        rating_val = item.get("averageRating", 0) or 0

        brand = ""
        if isinstance(item.get("brand"), str):
            brand = item["brand"]

        products.append(
            Product(
                source="walmart",
                url=product_url,
                title=name[:200],
                price=price,
                rating=str(rating_val),
                brand=brand,
                images=[image] if image else [],
            )
        )

    return products
