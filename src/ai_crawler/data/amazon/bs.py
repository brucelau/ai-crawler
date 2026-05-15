import re
from bs4 import BeautifulSoup

from ai_crawler.models.product import Product


def extract(html: str, url: str) -> list[Product]:
    soup = BeautifulSoup(html, "html.parser")
    items = [el for el in soup.select("[data-asin]") if el.get("data-asin")]
    products: list[Product] = []
    seen: set[str] = set()

    for item in items:
        asin = (item.get("data-asin") or "").strip()
        if not asin or asin in seen:
            continue

        title = ""
        for sel in [
            '[data-cy="title-recipe"]',
            "h2 a span",
            "h2 span",
            "a.a-link-normal.s-no-outline + h2 span",
        ]:
            el = item.select_one(sel)
            if el and el.get_text(" ", strip=True):
                title = el.get_text(" ", strip=True)
                break

        if not title or title.lower().startswith("results check"):
            continue

        link = ""
        for sel in ['a[href*="/dp/"]', "a.a-link-normal.s-no-outline"]:
            el = item.select_one(sel)
            href = el.get("href") if el else ""
            if href:
                link = href.split("?")[0]
                break
        if not link:
            link = f"https://www.amazon.com/dp/{asin}"
        elif link.startswith("/"):
            link = "https://www.amazon.com" + link

        price = ""
        price_el = item.select_one(".a-price .a-offscreen")
        if price_el and price_el.get_text(" ", strip=True):
            price = price_el.get_text(" ", strip=True).replace("$", "").replace(",", "")

        image = ""
        img = item.select_one("img.s-image")
        if img:
            image = img.get("src") or ""

        products.append(
            Product(
                source="amazon",
                url=link,
                title=title[:200],
                price=price,
                asin=asin,
                images=[image] if image else [],
            )
        )
        seen.add(asin)

    return products
