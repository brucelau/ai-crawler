"""Wowsports site adapter — search command (Shopify-based)."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ai_crawler.core.types import Product
from ai_crawler.sites.registry import Command, register


@register(site="wowsports", command="search")
class WowsportsSearch(Command):
    site = "wowsports"
    command = "search"
    url_template = "https://wowsports.com/search?q={query}"

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

        for item in soup.select("li.grid__item"):
            # Title and link from product links in card
            title = ""
            href = ""
            for a in item.select('a[href*="/products/"]'):
                txt = a.get_text(" ", strip=True)
                if len(txt) > 5 and len(txt) > len(title):
                    title = txt
                    href = a.get("href", "")
            if not title or len(title) < 5:
                continue

            if href.startswith("/"):
                href = "https://wowsports.com" + href
            if not href.startswith("http"):
                href = "https://wowsports.com/" + href.lstrip("/")
            if href in seen:
                continue
            seen.add(href)

            # Price from price-item elements
            price = ""
            sale = item.select_one(".price-item--sale")
            if sale:
                price = sale.get_text(strip=True)
            if not price:
                regular = item.select_one(".price-item--regular")
                if regular:
                    price = regular.get_text(strip=True)
            price = self._normalize_price(price) if price else ""

            # Image from card media
            image = ""
            img = item.select_one(".card__media img[alt]")
            if img:
                src = img.get("src") or img.get("data-src", "")
                if src and src.startswith("//"):
                    src = "https:" + src
                image = src

            # Rating from Okendo star rating
            rating = ""
            rating_el = item.select_one(".oke-sr-rating")
            if rating_el:
                rating = rating_el.get_text(strip=True)

            products.append(Product(
                source="wowsports",
                url=href,
                title=title[:200],
                price=price,
                images=[image] if image else [],
                rating=rating,
            ))

        return products
