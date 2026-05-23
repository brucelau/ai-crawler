"""eBay site adapter — search command."""

from __future__ import annotations

import re
from bs4 import BeautifulSoup

from ai_crawler.core.types import Product
from ai_crawler.sites.registry import Command, register


@register(site="ebay", command="search")
class EbaySearch(Command):
    site = "ebay"
    command = "search"
    url_template = "https://www.ebay.com/sch/i.html?_nkw={query}"

    start_level = 6

    def build_url(self, query: str, page: int = 1) -> str:
        from urllib.parse import quote_plus
        return self.url_template.format(query=quote_plus(query))

    def extract(self, html: str, url: str) -> list[Product]:
        soup = BeautifulSoup(html, "html.parser")
        items = [el for el in soup.select("[data-listingid]") if el.get("data-listingid")]
        products: list[Product] = []
        seen: set[str] = set()

        for item in items:
            listing_id = item.get("data-listingid", "").strip()
            if not listing_id or listing_id in seen:
                continue

            title = ""
            for sel in [".s-card__title", "h3", '[class*="title"]']:
                el = item.select_one(sel)
                if el and el.get_text(" ", strip=True):
                    title = el.get_text(" ", strip=True)
                    break
            if not title or title == "Shop on eBay":
                continue

            link = ""
            link_el = item.select_one('a[href*="/itm/"]')
            if link_el and link_el.get("href"):
                link = link_el.get("href").split("?")[0]

            price = ""
            price_el = item.select_one(".s-card__price, [class*=price]")
            if price_el and price_el.get_text(" ", strip=True):
                price = re.sub(r"[^\d.,]", "", price_el.get_text(" ", strip=True))

            image = ""
            img = item.select_one("img")
            if img:
                image = img.get("src") or img.get("data-src") or ""

            products.append(
                Product(
                    source="ebay",
                    url=link,
                    title=title[:200],
                    price=price,
                    images=[image] if image else [],
                )
            )
            seen.add(listing_id)

        return products

    def extract_detail(self, html: str, url: str) -> dict:
        """Extract product detail fields from an eBay item page."""
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)

        result: dict = {}

        # Price
        price_el = soup.select_one('[itemprop="price"]')
        if price_el:
            price = price_el.get("content") or price_el.get_text(strip=True)
            if price and "$" in price:
                result["price"] = self._normalize_price(price)

        # Condition
        m = re.search(r'Condition:\s*([^•\n]+)', text)
        if m:
            cond = m.group(1).strip()
            result["availability"] = cond[:80]

        # Brand
        m = re.search(r'Brand:\s*([^•\n]+)', text)
        if m:
            result["brand"] = m.group(1).strip()[:80]

        # Type / Category
        m = re.search(r'Type:\s*([^•\n]+)', text)
        if m:
            result["category"] = m.group(1).strip()[:80]

        # Seller
        m = re.search(r'Seller:\s*([^•\n]+)', text)
        if m:
            result["seller"] = m.group(1).strip()[:80]

        # Description — grab first meaningful paragraph
        for pattern in [r'About this item\s*(.+?)(?:Show less|Show more|Read more)',
                       r'Item description\s*(.+?)(?:Show less|Show more)']:
            m = re.search(pattern, text[:10000], re.DOTALL)
            if m:
                desc = re.sub(r'\s+', ' ', m.group(1).strip())[:500]
                if len(desc) > 20:
                    result["description"] = desc
                    break

        # Shipping
        m = re.search(r'Shipping:\s*([^•\n]+)', text)
        if m:
            result["shipping"] = m.group(1).strip()[:80]

        # Located in
        m = re.search(r'Located in:\s*([^•\n]+)', text)
        if m and "shipping" not in result:
            result["shipping"] = "Located in: " + m.group(1).strip()[:60]

        # Returns
        m = re.search(r'Returns:\s*([^•\n]+)', text)
        if m and "shipping" not in result:
            result["shipping"] = "Returns: " + m.group(1).strip()[:80]

        return result
