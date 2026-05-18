import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from ai_crawler.core.types import Product


def extract(html: str, url: str) -> list[Product]:
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.select('a[href*="/A-"], a[href*="/p/"]')
    products: list[Product] = []
    seen: set[str] = set()

    for anchor in anchors:
        href = (anchor.get("href") or "").split("#")[0].split("?")[0]
        title = (anchor.get("aria-label") or anchor.get_text(" ", strip=True) or "").strip()
        if not href or len(title) <= 5 or href in seen:
            continue
        seen.add(href)

        parent = anchor.find_parent(["li", "div", "section"])
        price_text = (
            parent.get_text(" ", strip=True) if parent else anchor.get_text(" ", strip=True)
        )
        price_match = re.search(r"\$([\d,]+\.?\d*)", price_text)
        price = price_match.group(1).replace(",", "") if price_match else ""

        image = ""
        img = anchor.select_one("img")
        if img:
            image = img.get("src") or img.get("data-src") or ""

        products.append(
            Product(
                source="target",
                url=urljoin("https://www.target.com", href),
                title=title[:200],
                price=price,
                images=[image] if image else [],
            )
        )

    return products
