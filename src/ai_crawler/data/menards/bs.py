import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from ai_crawler.models.product import Product


def extract(html: str, url: str) -> list[Product]:
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(".product-card, .product-item, .item-card")
    products: list[Product] = []
    seen: set[str] = set()

    for item in items:
        link_el = item.select_one('a[href*="/p/"], a[href*="/ip/"]')
        href = (link_el.get("href") if link_el else "") or ""
        href = href.split("?")[0]
        if not href or href in seen:
            continue

        title_el = item.select_one(".product-title, .item-title, .title, h3")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        if not title or len(title) <= 5:
            continue

        price_el = item.select_one(".price, .product-price, .item-price")
        price = ""
        if price_el:
            price_match = re.search(r"\$?([\d,]+\.?\d*)", price_el.get_text(" ", strip=True))
            if price_match:
                price = price_match.group(1).replace(",", "")

        img = item.select_one("img")
        image = img.get("src") or img.get("data-src") or "" if img else ""

        products.append(
            Product(
                source="menards",
                url=urljoin("https://www.menards.com", href),
                title=title[:200],
                price=price,
                images=[image] if image else [],
            )
        )
        seen.add(href)

    return products