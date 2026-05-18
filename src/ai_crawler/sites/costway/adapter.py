"""Costway site adapter — search command."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ai_crawler.core.types import Product
from ai_crawler.sites.registry import Command, register


@register(site="costway", command="search")
class CostwaySearch(Command):
    site = "costway"
    command = "search"
    url_template = "https://www.costway.com/search?q={query}"

    start_level = 0
    pagination = "query_param"
    page_param = "page"

    def build_url(self, query: str, page: int = 1) -> str:
        from urllib.parse import quote_plus
        url = self.url_template.format(query=quote_plus(query))
        if page > 1:
            url += f"&page={page}"
        return url

    def extract(self, html: str, url: str) -> list[Product]:
        soup = BeautifulSoup(html, "html.parser")
        products: list[Product] = []
        seen: set[str] = set()

        for item in soup.select("li.product-item"):
            # Title and link from h2 > a
            title_el = item.select_one("h2.product-title a")
            if not title_el:
                continue
            title = title_el.get_text(" ", strip=True)
            if not title or len(title) < 5:
                continue

            href = title_el.get("href", "")
            if href.startswith("/"):
                href = "https://www.costway.com" + href
            if href in seen:
                continue
            seen.add(href)

            # Price
            price = ""
            special = item.select_one("span.special-price")
            if special:
                price = special.get_text(strip=True)

            # Image
            image = ""
            img = item.select_one(".product-images img[alt]")
            if img:
                image = img.get("src") or ""

            # Rating
            rating = ""
            star = item.select_one(".star-num")
            if star:
                rating = star.get_text(strip=True)

            products.append(Product(
                source="costway",
                url=href,
                title=title[:200],
                price=price,
                images=[image] if image else [],
                rating=rating,
            ))

        return products
