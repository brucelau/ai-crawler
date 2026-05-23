#!/usr/bin/env python3
"""Batch-generate adapter files for all sites that don't have one."""
import os

SITES_DIR = os.path.dirname(os.path.abspath(__file__)) + "/../src/ai_crawler/sites"

SITES = {
    "homedepot": {
        "url": "https://www.homedepot.com/s/{query}",
        "selectors": ["[data-testid='product-pod']", ".product-pod", ".grid-item"],
        "title_sel": [".product-title", ".product-pod__title", "h3"],
        "price_sel": [".price", ".product-pod__price", "[data-testid='price']"],
        "link_sel": ["a[href*='/p/']", "a[href*='/product/']"],
    },
    "lowes": {
        "url": "https://www.lowes.com/search?searchTerm={query}",
        "selectors": ["[data-testid='product-card']", ".product-card", ".grid-item"],
        "title_sel": [".product-title", "h3", ".description"],
        "price_sel": [".product-price", ".price", "[data-testid='price']"],
        "link_sel": ["a[href*='/pd/']", "a[href*='/product/']"],
    },
    "kohls": {
        "url": "https://www.kohls.com/search.jsp?search={query}",
        "selectors": [".product-card", "[data-testid='product-card']", ".products-grid li"],
        "title_sel": [".product-title", ".prod_name", "h3"],
        "price_sel": [".product-price", ".prod_price", ".price"],
        "link_sel": ["a[href*='/p/']", "a[href*='/product/']"],
    },
    "etsy": {
        "url": "https://www.etsy.com/search?q={query}",
        "selectors": ["[data-search-results] li", ".listing-card", ".v2-listing-card"],
        "title_sel": [".v2-listing-card__title", ".listing-card__title", "h3"],
        "price_sel": [".currency-value", ".lc-price .currency-value", ".n-listing-card__price"],
        "link_sel": ["a[href*='/listing/']"],
    },
    "michaels": {
        "url": "https://www.michaels.com/search?q={query}",
        "selectors": [".product-tile", "[data-testid='product-tile']"],
        "title_sel": [".product-title", ".name", "h3"],
        "price_sel": [".product-price", ".price", ".regular-price"],
        "link_sel": ["a[href*='/p/']", "a[href*='/product/']"],
    },
    "samsclub": {
        "url": "https://www.samsclub.com/s/{query}",
        "selectors": ["[data-testid='product-card']", ".sc-product-card"],
        "title_sel": [".sc-product-title", "h4", ".product-title"],
        "price_sel": [".sc-price", ".price", ".product-price"],
        "link_sel": ["a[href*='/p/']", "a[href*='/prod/']"],
    },
    "dollargeneral": {
        "url": "https://www.dollargeneral.com/search?q={query}",
        "selectors": [".product-tile", ".product-card", ".search-result-item"],
        "title_sel": [".product-name", "h3", ".title"],
        "price_sel": [".price", ".sale-price", ".product-price"],
        "link_sel": ["a[href*='/p/']", "a[href*='/product/']"],
    },
    "familydollar": {
        "url": "https://www.familydollar.com/search?q={query}",
        "selectors": [".product-tile", ".product-card"],
        "title_sel": [".product-title", "h3"],
        "price_sel": [".price", ".product-price"],
        "link_sel": ["a[href*='/p/']", "a[href*='/product/']"],
    },
    "fivebelow": {
        "url": "https://www.fivebelow.com/search?q={query}",
        "selectors": [".product-tile", ".product-card", ".search-result"],
        "title_sel": [".product-title", "h3"],
        "price_sel": [".price", ".product-price"],
        "link_sel": ["a[href*='/p/']", "a[href*='/product/']"],
    },
    "academy": {
        "url": "https://www.academy.com/search?q={query}",
        "selectors": [".product-tile", ".product-card", "[data-testid='product-card']"],
        "title_sel": [".product-title", "h3"],
        "price_sel": [".price", ".product-price"],
        "link_sel": ["a[href*='/p/']", "a[href*='/product/']"],
    },
    "acehardware": {
        "url": "https://www.acehardware.com/search?query={query}",
        "selectors": [".product-tile", ".product-card"],
        "title_sel": [".product-title", "h3"],
        "price_sel": [".price", ".product-price"],
        "link_sel": ["a[href*='/p/']", "a[href*='/product/']"],
    },
    "menards": {
        "url": "https://www.menards.com/main/search.html?search={query}",
        "selectors": [".product-card", ".search-result", ".product-tile"],
        "title_sel": [".product-title", "h3"],
        "price_sel": [".price", ".product-price"],
        "link_sel": ["a[href*='/p/']", "a[href*='/product/']"],
    },
    "meijer": {
        "url": "https://www.meijer.com/shopping/search.html?text={query}",
        "selectors": [".product-tile", ".product-card"],
        "title_sel": [".product-title", "h3"],
        "price_sel": [".price", ".product-price"],
        "link_sel": ["a[href*='/p/']", "a[href*='/product/']"],
    },
    "bunnings": {
        "url": "https://www.bunnings.com.au/search/products?q={query}",
        "selectors": [".product-tile", ".product-card", ".search-result"],
        "title_sel": [".product-title", "h3"],
        "price_sel": [".price", ".product-price"],
        "link_sel": ["a[href*='/p/']", "a[href*='/product/']"],
    },
    "mercadolibre": {
        "url": "https://listado.mercadolibre.com/{query}",
        "selectors": [".ui-search-result", ".andes-card", "li.ui-search-layout__item"],
        "title_sel": [".ui-search-item__title", "h2"],
        "price_sel": [".price-tag-fraction", ".andes-money-amount__fraction", ".ui-search-price__second-line"],
        "link_sel": ["a[href*='/ML']", "a[href*='/p/']"],
    },
    "walmartmexico": {
        "url": "https://www.walmart.com.mx/busca?q={query}",
        "selectors": [".product-card", "[data-testid='product-card']"],
        "title_sel": [".product-title", "h3"],
        "price_sel": [".price", ".product-price"],
        "link_sel": ["a[href*='/p/']", "a[href*='/product/']"],
    },
    "temu": {
        "url": "https://www.temu.com/search_result.html?search_key={query}",
        "selectors": [".search-results-container .goods-card", ".product-card"],
        "title_sel": [".goods-title", "h3"],
        "price_sel": [".goods-price", ".price"],
        "link_sel": ["a[href*='/goods/']", "a[href*='/product/']"],
    },
    "qvc": {
        "url": "https://www.qvc.com/catalog/search.html?keyword={query}",
        "selectors": [".product-tile", ".product-card"],
        "title_sel": [".product-title", "h3"],
        "price_sel": [".price", ".product-price"],
        "link_sel": ["a[href*='/p/']", "a[href*='/product/']"],
    },
    "coppel": {
        "url": "https://www.coppel.com/buscar?q={query}",
        "selectors": [".product-tile", ".product-card"],
        "title_sel": [".product-title", "h3"],
        "price_sel": [".price", ".product-price"],
        "link_sel": ["a[href*='/p/']", "a[href*='/product/']"],
    },
    "aosom": {
        "url": "https://www.aosom.com/search?q={query}",
        "selectors": [".product-tile", ".product-card"],
        "title_sel": [".product-title", "h3"],
        "price_sel": [".price", ".product-price"],
        "link_sel": ["a[href*='/p/']", "a[href*='/product/']"],
    },
    "intexcorp": {
        "url": "https://intexcorp.com/search?q={query}",
        "selectors": [".product-tile", ".product-card", ".product"],
        "title_sel": [".product-title", "h3", ".product-name"],
        "price_sel": [".price", ".product-price"],
        "link_sel": ["a[href*='/p/']", "a[href*='/product/']"],
    },
    "action": {
        "url": "https://www.action.com/en/search/?q={query}",
        "selectors": [".product-tile", ".product-card", ".search-result"],
        "title_sel": [".product-title", "h3"],
        "price_sel": [".price", ".product-price"],
        "link_sel": ["a[href*='/p/']", "a[href*='/product/']"],
    },
}

TEMPLATE = '''"""{site_title} site adapter — search command."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ai_crawler.core.types import Product
from ai_crawler.sites.registry import Command, register


@register(site="{site}", command="search")
class {class_name}(Command):
    site = "{site}"
    command = "search"
    url_template = "{url_template}"

    start_level = 6

    def build_url(self, query: str, page: int = 1) -> str:
        from urllib.parse import quote_plus
        return self.url_template.format(query=quote_plus(query))

    def extract(self, html: str, url: str) -> list[Product]:
        soup = BeautifulSoup(html, "html.parser")
        products: list[Product] = []
        seen: set[str] = set()

        # Try selectors in priority order
        items = []
        for sel in {selectors!r}:
            items = soup.select(sel)
            if items:
                break

        if not items:
            # Fallback: grab all links that look like product URLs
            items = soup.select('a[href*="/p/"], a[href*="/product/"], a[href*="/goods/"], a[href*="/item/"], a[href*="/listing/"], a[href*="/ip/"], a[href*="/pd/"]')
            items = [el.parent for el in items if el.parent]

        for item in items:
            # Title
            title = ""
            for sel in {title_selectors!r}:
                el = item.select_one(sel)
                if el and el.get_text(" ", strip=True):
                    title = el.get_text(" ", strip=True)
                    break
            if not title or len(title) < 5:
                continue

            # Link
            link = ""
            for sel in {link_selectors!r}:
                link_el = item.select_one(sel)
                if link_el and link_el.get("href"):
                    link = link_el.get("href").split("?")[0]
                    break
            if not link:
                link_el = item.select_one("a[href]")
                if link_el:
                    link = link_el.get("href", "").split("?")[0]
            if link and link.startswith("/"):
                link = urljoin(url, link)
            if not link or link in seen:
                continue

            # Price
            price = ""
            for sel in {price_selectors!r}:
                el = item.select_one(sel)
                if el:
                    price = re.sub(r"[^\\d.,]", "", el.get_text(" ", strip=True))
                    if price:
                        break

            # Image
            image = ""
            img = item.select_one("img")
            if img:
                image = img.get("src") or img.get("data-src") or ""

            products.append(Product(
                source="{site}",
                url=link,
                title=title[:200],
                price=price,
                images=[image] if image else [],
            ))
            seen.add(link)

        return products

    def extract_detail(self, html: str, url: str) -> dict:
        """Extract product detail fields from a {site_title} product page."""
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        result: dict = {{}}

        # Price
        m = re.search(r'\\$(\\d+(?:,\\d{{3}})*\\.?\\d{{0,2}})', text)
        if m:
            result["price"] = m.group(0)

        # Brand
        for pattern in [r'[Bb]rand:\\s*([^\\n\\u2022]+)', r'[Bb]y\\s+([A-Z][a-zA-Z0-9\\s&.-]{{2,30}})']:
            m = re.search(pattern, text[:5000])
            if m:
                result["brand"] = m.group(1).strip()[:80]
                break

        # Description
        for pattern in [r'(?:Description|Overview|About this item)\\s*(.+?)(?:Specs|Features|Details|What.s Included)', r'(?:Product Details|Item Description)\\s*(.+?)(?:Specs|Features|Shipping)']:
            m = re.search(pattern, text[:10000], re.DOTALL)
            if m:
                desc = re.sub(r'\\s+', ' ', m.group(1).strip())[:500]
                if len(desc) > 30:
                    result["description"] = desc
                    break

        return result
'''

for site, cfg in SITES.items():
    site_dir = os.path.join(SITES_DIR, site)
    adapter_path = os.path.join(site_dir, "adapter.py")
    if os.path.exists(adapter_path):
        print(f"SKIP {site} (already exists)")
        continue

    os.makedirs(site_dir, exist_ok=True)
    class_name = "".join(w.capitalize() for w in site.replace("-", " ").split()) + "Search"
    site_title = " ".join(w.capitalize() for w in site.replace("-", " ").split())

    content = TEMPLATE.format(
        site=site,
        class_name=class_name,
        site_title=site_title,
        url_template=cfg["url"],
        selectors=cfg["selectors"],
        title_selectors=cfg["title_sel"],
        price_selectors=cfg["price_sel"],
        link_selectors=cfg["link_sel"],
    )

    with open(adapter_path, "w") as f:
        f.write(content)
    print(f"CREATED {site}/adapter.py")

print("\nDone!")
