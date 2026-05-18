"""Amazon site adapter — search and product commands."""

from __future__ import annotations

from bs4 import BeautifulSoup

from ai_crawler.core.types import Product
from ai_crawler.sites.registry import Command, register

# JS eval code for dynamic extraction (from js.py)
JS_CODE = """
(() => {
    const items = document.querySelectorAll('[data-asin]');
    return Array.from(items).map(el => {
        const asin = el.getAttribute('data-asin');
        const titleEl = el.querySelector('span.a-text-normal') || el.querySelector('h2 a span');
        const priceEl = el.querySelector('.a-price .a-offscreen');
        const ratingEl = el.querySelector('.a-icon-star-small');
        const imgEl = el.querySelector('img.s-image');
        return {
            title: titleEl ? titleEl.textContent.trim() : '',
            price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
            asin: asin || '',
            url: asin ? 'https://www.amazon.com/dp/' + asin : '',
            image: imgEl ? imgEl.src : ''
        };
    }).filter(p => p.title && p.asin);
})()
"""


@register(site="amazon", command="search")
class AmazonSearch(Command):
    site = "amazon"
    command = "search"
    url_template = "https://www.amazon.com/s?k={query}&page={page}"

    start_level = 1
    pagination = "query_param"
    page_param = "page"

    def build_url(self, query: str, page: int = 1) -> str:
        from urllib.parse import quote_plus
        return self.url_template.format(query=quote_plus(query), page=page)

    def extract(self, html: str, url: str) -> list[Product]:
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
                price = self._normalize_price(price_el.get_text(" ", strip=True))

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

    async def extract_dynamic(self, page, url: str) -> list[Product]:
        items = await page.evaluate(JS_CODE)
        return [
            Product(
                source="amazon",
                url=item["url"],
                title=item["title"][:200],
                price=item.get("price", ""),
                asin=item.get("asin", ""),
                images=[item["image"]] if item.get("image") else [],
            )
            for item in items
        ]


@register(site="amazon", command="product")
class AmazonProduct(Command):
    site = "amazon"
    command = "product"
    url_template = "https://www.amazon.com/dp/{asin}"
    start_level = 0

    def build_url(self, asin: str) -> str:
        return self.url_template.format(asin=asin)

    def extract(self, html: str, url: str) -> list[Product]:
        soup = BeautifulSoup(html, "html.parser")

        title = ""
        title_el = soup.select_one("#productTitle") or soup.select_one("#title")
        if title_el:
            title = title_el.get_text(" ", strip=True)

        price = ""
        for sel in [
            ".a-price .a-offscreen",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            ".a-price-whole",
        ]:
            el = soup.select_one(sel)
            if el and el.get_text(" ", strip=True):
                price = self._normalize_price(el.get_text(" ", strip=True))
                break

        image = ""
        img = soup.select_one("#landingImage") or soup.select_one("img#imgTagWrapperId img")
        if img:
            image = img.get("src") or ""

        asin = ""
        asin_el = soup.select_one('[data-asin]') or soup.select_one('input[name="ASIN"]')
        if asin_el:
            asin = (asin_el.get("data-asin") or asin_el.get("value") or "").strip()
        if not asin:
            import re
            m = re.search(r"/dp/([A-Z0-9]{10})", url)
            if m:
                asin = m.group(1)

        description = ""
        desc_el = soup.select_one("#feature-bullets") or soup.select_one("#productDescription")
        if desc_el:
            description = desc_el.get_text(" ", strip=True)[:500]

        rating = ""
        rating_el = soup.select_one('[data-hook="rating-out-of-text"]') or soup.select_one(".a-icon-star .a-icon-alt")
        if rating_el:
            rating = rating_el.get_text(" ", strip=True)

        return [Product(
            source="amazon",
            url=url,
            title=title[:200],
            price=price,
            asin=asin,
            images=[image] if image else [],
            description=description,
            rating=rating,
        )] if title else []
