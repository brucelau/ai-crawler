import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from ai_crawler.core.types import Product


def extract(html: str, url: str) -> list[Product]:
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(".product-item")
    products: list[Product] = []
    seen: set[str] = set()

    for item in items:
        link_el = item.select_one('.product-images a[href$=".html"], a[href$=".html"]')
        href = (link_el.get("href") if link_el else "") or "" if link_el else ""
        if not href:
            continue
        href = href.split("?")[0]
        if href in seen:
            continue

        title = ""
        img_el = item.select_one('img[alt]')
        if img_el:
            title = img_el.get("alt", "").strip()
        if not title:
            title_el = item.select_one('[class*="title"], [class*="name"]')
            if title_el:
                title = title_el.get_text(" ", strip=True)
        if not title or len(title) <= 5:
            continue

        price = ""
        price_el = item.select_one(".price")
        if price_el:
            price_text = price_el.get_text(" ", strip=True)
            price_match = re.search(r"\$?([\d,]+\.?\d*)", price_text)
            if price_match:
                price = price_match.group(1).replace(",", "")

        image = ""
        img = item.select_one("img")
        if img:
            image = img.get("src") or img.get("data-src") or ""

        products.append(
            Product(
                source="costway",
                url=urljoin("https://www.costway.com", href),
                title=title[:200],
                price=price,
                images=[image] if image else [],
            )
        )
        seen.add(href)

    return products
