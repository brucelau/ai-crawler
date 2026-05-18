"""Wayfair site adapter — search command."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ai_crawler.core.types import Product
from ai_crawler.sites.registry import Command, register


@register(site="wayfair", command="search")
class WayfairSearch(Command):
    site = "wayfair"
    command = "search"
    url_template = "https://www.wayfair.com/keyword.php?keyword={query}"

    start_level = 1
    pagination = "query_param"
    page_param = "page"

    def build_url(self, query: str, page: int = 1) -> str:
        from urllib.parse import quote_plus
        url = self.url_template.format(query=quote_plus(query))
        if page > 1:
            url += f"&page={page}"
        return url

    # Brand/promo link texts that are not product titles
    _NOT_TITLES = {
        "memorial day deal", "bundle & save", "spend & save", "add to cart",
        "quick view", "save", "sponsored", "best seller", "new", "open box",
        "flash deal", "limited time deal", "price drop",
    }

    def extract(self, html: str, url: str) -> list[Product]:
        soup = BeautifulSoup(html, "html.parser")
        products: list[Product] = []
        seen: set[str] = set()

        for link in soup.select('a[href*="/pdp/"]'):
            href = link.get("href", "")
            if not href or "/pdp/" not in href:
                continue

            product_url = href.split("?")[0]
            if product_url.startswith("/"):
                product_url = "https://www.wayfair.com" + product_url
            if product_url in seen:
                continue
            seen.add(product_url)

            # Climb up to card container first
            card = link
            for _ in range(8):
                card = card.parent
                if card is None:
                    break
                card_text = card.get_text()
                if len(card_text) > 200:
                    break

            if card is None:
                continue

            # Find the real product title within the card, not the link text
            # (the link might be a promo badge, the actual title is longer)
            title = ""
            for el in card.select("a[href*='/pdp/']"):
                txt = el.get_text(" ", strip=True)
                skip = txt.strip().lower() in self._NOT_TITLES
                if not skip and len(txt) > len(title):
                    title = txt
            if not title or len(title) < 10:
                continue

            # Price
            price = ""
            card_text = card.get_text(" ", strip=True)
            m = re.search(r'\$(\d+(?:,\d{3})*\.?\d{0,2})', card_text)
            if m:
                price = m.group(0)

            # Image
            image = ""
            for img in card.select("img[src]"):
                src = img.get("src", "")
                alt = img.get("alt", "").strip()
                if alt and len(alt) > 5 and alt[:20].lower() in title.lower()[:20]:
                    image = src
                    break
            if not image:
                for img in card.select("img[src]"):
                    src = img.get("src", "")
                    if src and not src.endswith(".svg") and "logo" not in src.lower():
                        image = src
                        break

            products.append(Product(
                source="wayfair",
                url=product_url,
                title=title[:200],
                price=price,
                images=[image] if image else [],
            ))

        return products
