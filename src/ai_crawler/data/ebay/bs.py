import re
from bs4 import BeautifulSoup

from ai_crawler.models.product import Product


def extract(html: str, url: str) -> list[Product]:
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
