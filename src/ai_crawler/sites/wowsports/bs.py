import re
from bs4 import BeautifulSoup

from ai_crawler.core.types import Product


def extract(html: str, url: str) -> list[Product]:
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("main .grid__item, main .card-wrapper")
    products: list[Product] = []
    seen: set[str] = set()

    for item in items:
        link_el = item.select_one('a.full-unstyled-link[href*="/products/"]')
        href = (link_el.get("href") if link_el else "") or ""
        href = href.split("?")[0]
        if not href or href in seen:
            continue

        title = ""
        title_el = item.select_one('.card__heading, [class*="card__heading"]')
        if title_el and title_el.get_text(" ", strip=True):
            title = title_el.get_text(" ", strip=True)
        if not title or len(title) <= 5:
            continue

        price = ""
        price_el = item.select_one('.price, [class*="price"]')
        if price_el and price_el.get_text(" ", strip=True):
            price = re.sub(r"[^\d.,]", "", price_el.get_text(" ", strip=True))

        image = ""
        img = item.select_one("img")
        if img:
            image = img.get("src") or img.get("data-src") or ""

        products.append(
            Product(
                source="wowsports",
                url=f"https://wowsports.com{href}",
                title=title[:200],
                price=price,
                images=[image] if image else [],
            )
        )
        seen.add(href)

    return products
