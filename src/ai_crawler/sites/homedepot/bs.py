import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from ai_crawler.core.types import Product


def extract(html: str, url: str) -> list[Product]:
    soup = BeautifulSoup(html, "html.parser")
    selector_groups = [
        "[data-pod-type='product'], .product-card, .product-pod",
        "[data-item-id]",
        "li[class*='product']",
        "[data-testid='product-card']",
        "article[class*='product']",
        "[itemtype*='Product']",
        ".search-results li",
        "#search-results li",
    ]
    items = []
    for selector in selector_groups:
        items = soup.select(selector)
        if items:
            break

    if not items:
        products = []
        anchors = soup.select('a[href*="/p/"], a[href*="/ip/"]')
        seen = set()
        for anchor in anchors:
            href = (anchor.get("href") or "").split("?")[0].split("#")[0]
            if not href or href in seen:
                continue
            seen.add(href)
            title = anchor.get("aria-label") or anchor.get_text(" ", strip=True) or ""
            if len(title) <= 5:
                continue
            parent = anchor.find_parent(["li", "div", "article", "section"])
            price_text = parent.get_text(" ", strip=True) if parent else ""
            price_match = re.search(r"\$?([\d,]+\.?\d*)", price_text)
            price = price_match.group(1).replace(",", "") if price_match else ""
            img = parent.select_one("img") if parent else None
            image = img.get("src") or img.get("data-src") or "" if img else ""
            products.append(
                Product(
                    source="homedepot",
                    url=urljoin("https://www.homedepot.com", href),
                    title=title[:200],
                    price=price,
                    images=[image] if image else [],
                )
            )
        return products

    products: list[Product] = []
    seen: set[str] = set()

    for item in items:
        link_el = item.select_one('a[href*="/p/"], a[href*="/ip/"]')
        href = (link_el.get("href") if link_el else "") or ""
        href = href.split("?")[0]
        if not href or href in seen:
            continue

        title_el = item.select_one("[data-testid='product-title'], .product-card__title, .pod-title, h3, [class*='title']")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        if not title or len(title) <= 5:
            continue

        price_el = item.select_one("[data-testid='product-price'], .product-card__price, .price-format, [class*='price']")
        price = ""
        if price_el:
            price_match = re.search(r"\$?([\d,]+\.?\d*)", price_el.get_text(" ", strip=True))
            if price_match:
                price = price_match.group(1).replace(",", "")

        img = item.select_one("img")
        image = img.get("src") or img.get("data-src") or "" if img else ""

        products.append(
            Product(
                source="homedepot",
                url=urljoin("https://www.homedepot.com", href),
                title=title[:200],
                price=price,
                images=[image] if image else [],
            )
        )
        seen.add(href)

    return products