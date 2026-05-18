import re
from bs4 import BeautifulSoup

from ai_crawler.core.types import Product


def extract(html: str, url: str) -> list[Product]:
    soup = BeautifulSoup(html, "html.parser")
    links = soup.select('a[href*="/furniture/pdp/"]')
    containers: list = []
    for link in links:
        container = link.find_parent(["div", "article", "section", "li"])
        if container and container not in containers:
            containers.append(container)

    products_by_url: dict[str, Product] = {}
    ignore_titles = {"30-day low price", "tax refund sale", "bundle and save"}

    for container in containers:
        candidate_links = container.select('a[href*="/furniture/pdp/"]')
        best_href = ""
        best_title = ""
        for link_el in candidate_links:
            href = (link_el.get("href") or "").split("?")[0]
            title = (
                link_el.get("aria-label") or link_el.get_text(" ", strip=True) or ""
            ).strip()
            if not href:
                continue
            if title and title.lower() not in ignore_titles and len(title) > len(best_title):
                best_title = title
                best_href = href

        href = best_href
        title = best_title
        if not href or not title or title.lower() in ignore_titles or len(title) <= 8:
            continue
        container_text = container.get_text(" ", strip=True)
        price_match = re.search(r"\$\s*([\d,]+(?:\.\d{2})?)", container_text)
        price = price_match.group(1).replace(",", "") if price_match else ""

        image = ""
        img = container.select_one("img[alt]")
        if img:
            image = img.get("src") or img.get("data-src") or ""

        product = Product(
            source="wayfair",
            url=href if href.startswith("http") else "https://www.wayfair.com" + href,
            title=title[:200],
            price=price,
            images=[image] if image else [],
        )
        existing = products_by_url.get(product.url)
        if existing is None or len(product.title) > len(existing.title):
            products_by_url[product.url] = product

    return list(products_by_url.values())
