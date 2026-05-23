"""Temu site adapter — search command."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ai_crawler.core.types import Product
from ai_crawler.sites.registry import Command, register


@register(site="temu", command="search")
class TemuSearch(Command):
    site = "temu"
    command = "search"
    url_template = "https://www.temu.com/search_result.html?search_key={query}"

    start_level = 6

    def build_url(self, query: str, page: int = 1) -> str:
        from urllib.parse import quote_plus
        return self.url_template.format(query=quote_plus(query))

    def extract(self, html: str, url: str) -> list[Product]:
        soup = BeautifulSoup(html, "html.parser")
        products: list[Product] = []
        seen: set[str] = set()

        # Try selectors in priority order
        items = []
        for sel in ['.search-results-container .goods-card', '.product-card']:
            items = soup.select(sel)
            if items:
                break

        if not items:
            # Fallback: grab all links that look like product URLs
            items = soup.select('a[href*="/p/"], a[href*="/product/"], a[href*="/goods/"], a[href*="/item/"], a[href*="/listing/"], a[href*="/ip/"], a[href*="/pd/"]')
            items = [el.parent for el in items if el.parent]

        for item in items:
            # Title
            title = ""
            for sel in ['.goods-title', 'h3']:
                el = item.select_one(sel)
                if el and el.get_text(" ", strip=True):
                    title = el.get_text(" ", strip=True)
                    break
            if not title or len(title) < 5:
                continue

            # Link
            link = ""
            for sel in ["a[href*='/goods/']", "a[href*='/product/']"]:
                link_el = item.select_one(sel)
                if link_el and link_el.get("href"):
                    link = link_el.get("href").split("?")[0]
                    break
            if not link:
                link_el = item.select_one("a[href]")
                if link_el:
                    link = link_el.get("href", "").split("?")[0]
            if link and link.startswith("/"):
                link = urljoin(url, link)
            if not link or link in seen:
                continue

            # Price
            price = ""
            for sel in ['.goods-price', '.price']:
                el = item.select_one(sel)
                if el:
                    price = re.sub(r"[^\d.,]", "", el.get_text(" ", strip=True))
                    if price:
                        break

            # Image
            image = ""
            img = item.select_one("img")
            if img:
                image = img.get("src") or img.get("data-src") or ""

            products.append(Product(
                source="temu",
                url=link,
                title=title[:200],
                price=price,
                images=[image] if image else [],
            ))
            seen.add(link)

        return products

    def extract_detail(self, html: str, url: str) -> dict:
        """Extract product detail fields from a Temu product page."""
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        result: dict = {}

        # Price
        m = re.search(r'\$(\d+(?:,\d{3})*\.?\d{0,2})', text)
        if m:
            result["price"] = m.group(0)

        # Brand
        for pattern in [r'[Bb]rand:\s*([^\n\u2022]+)', r'[Bb]y\s+([A-Z][a-zA-Z0-9\s&.-]{2,30})']:
            m = re.search(pattern, text[:5000])
            if m:
                result["brand"] = m.group(1).strip()[:80]
                break

        # Description
        for pattern in [r'(?:Description|Overview|About this item)\s*(.+?)(?:Specs|Features|Details|What.s Included)', r'(?:Product Details|Item Description)\s*(.+?)(?:Specs|Features|Shipping)']:
            m = re.search(pattern, text[:10000], re.DOTALL)
            if m:
                desc = re.sub(r'\s+', ' ', m.group(1).strip())[:500]
                if len(desc) > 30:
                    result["description"] = desc
                    break

        return result
