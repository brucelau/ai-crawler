import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from ai_crawler.core.types import Product


def extract(html: str, url: str) -> list[Product]:
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("[data-testid='product-card'], .sku-item, .product-item")
    products: list[Product] = []
    seen: set[str] = set()

    for item in items:
        link_el = item.select_one('a[href*="/p/"], a[href*="/sku/"]')
        href = (link_el.get("href") if link_el else "") or ""
        href = href.split("?")[0]
        if not href or href in seen:
            continue

        title_el = item.select_one("[data-testid='product-title'], .sku-title, .product-title, h3")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        if not title or len(title) <= 5:
            continue

        price_el = item.select_one("[data-testid='product-price'], .price, .sku-price")
        price = ""
        if price_el:
            price_match = re.search(r"\$?([\d,]+\.?\d*)", price_el.get_text(" ", strip=True))
            if price_match:
                price = price_match.group(1).replace(",", "")

        img = item.select_one("img")
        image = img.get("src") or img.get("data-src") or "" if img else ""

        products.append(
            Product(
                source="bestbuy",
                url=urljoin("https://www.bestbuy.com", href),
                title=title[:200],
                price=price,
                images=[image] if image else [],
            )
        )
        seen.add(href)

    return products