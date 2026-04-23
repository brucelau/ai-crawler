import re
from typing import Any

from ai_crawler.core.extraction.base import ExtractionStrategy
from ai_crawler.models.product import Product
from ai_crawler.utils.site import infer_site_from_url_or_empty


class BSExtraction(ExtractionStrategy):
    name = "bs_css"
    method = "beautifulsoup"

    def __init__(self):
        super().__init__(name=self.name, method=self.method)

    def extract(self, page: Any, html: str, url: str) -> list[Product]:
        from ai_crawler.spiders import EXTRACTORS

        source = self._infer_source(url)
        extractor = EXTRACTORS.get(source, {}).get("list")
        if extractor:
            try:
                return extractor(html, url)
            except Exception:
                log.warning("bs_extraction_failed", source=source, url=url)
                return []

        if source == "amazon":
            return self._extract_amazon_search(html)
        if source == "ebay":
            return self._extract_ebay_search(html)
        if source == "target":
            return self._extract_target_search(html, url)
        if source == "wowsports":
            return self._extract_wowsports_search(html)
        if source == "costway":
            return self._extract_costway_search(html)
        if source == "wayfair":
            return self._extract_wayfair_search(html)
        if source == "homedepot":
            return self._extract_homedepot_search(html)
        if source == "lowes":
            return self._extract_lowes_search(html)
        if source == "kohls":
            return self._extract_kohls_search(html)
        if source == "michaels":
            return self._extract_michaels_search(html)
        if source == "qvc":
            return self._extract_qvc_search(html)
        if source == "bestbuy":
            return self._extract_bestbuy_search(html)
        if source == "costco":
            return self._extract_costco_search(html)
        if source == "samsclub":
            return self._extract_samsclub_search(html)
        if source == "menards":
            return self._extract_menards_search(html)
        if source == "mercadolibre":
            return self._extract_mercadolibre_search(html)
        return []

    def _infer_source(self, url: str) -> str:
        return infer_site_from_url_or_empty(url)

    def _extract_target_search(self, html: str, url: str) -> list[Product]:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

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

    def _extract_ebay_search(self, html: str) -> list[Product]:
        from bs4 import BeautifulSoup

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

    def _extract_wowsports_search(self, html: str) -> list[Product]:
        from bs4 import BeautifulSoup

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
                    url="https://wowsports.com" + href,
                    title=title[:200],
                    price=price,
                    images=[image] if image else [],
                )
            )
            seen.add(href)

        return products

    def _extract_costway_search(self, html: str) -> list[Product]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        items = soup.select(".product-item")
        products: list[Product] = []
        seen: set[str] = set()

        for item in items:
            link_el = item.select_one('.product-images a[href$=".html"], a[href$=".html"]')
            href = (link_el.get("href") if link_el else "") or ""
            href = href.split("?")[0]
            if not href or href in seen:
                continue

            title = ""
            img = item.select_one("img[alt]")
            if img and img.get("alt"):
                title = img.get("alt").strip()
            if not title:
                title_el = item.select_one('[class*="title"], [class*="name"]')
                if title_el and title_el.get_text(" ", strip=True):
                    title = title_el.get_text(" ", strip=True)
            if not title or len(title) <= 5:
                continue

            price = ""
            price_el = item.select_one('.price, [class*="price"]')
            if price_el and price_el.get_text(" ", strip=True):
                price = re.sub(r"[^\d.,]", "", price_el.get_text(" ", strip=True))

            image = img.get("src") if img else ""
            products.append(
                Product(
                    source="costway",
                    url="https://www.costway.com" + href,
                    title=title[:200],
                    price=price,
                    images=[image] if image else [],
                )
            )
            seen.add(href)

        return products

    def _extract_wayfair_search(self, html: str) -> list[Product]:
        from bs4 import BeautifulSoup

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

    def _extract_amazon_search(self, html: str) -> list[Product]:
        from bs4 import BeautifulSoup

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

    def _extract_homedepot_search(self, html: str) -> list[Product]:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

        soup = BeautifulSoup(html, "html.parser")
        items = soup.select("[data-pod-type='product'], .product-card, .product-pod")
        products: list[Product] = []
        seen: set[str] = set()

        for item in items:
            link_el = item.select_one('a[href*="/p/"], a[href*="/ip/"]')
            href = (link_el.get("href") if link_el else "") or ""
            href = href.split("?")[0]
            if not href or href in seen:
                continue

            title_el = item.select_one("[data-testid='product-title'], .product-card__title, .pod-title")
            title = title_el.get_text(" ", strip=True) if title_el else ""
            if not title or len(title) <= 5:
                continue

            price_el = item.select_one("[data-testid='product-price'], .product-card__price, .price-format")
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

    def _extract_lowes_search(self, html: str) -> list[Product]:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

        soup = BeautifulSoup(html, "html.parser")
        items = soup.select("[data-testid='product-card'], .product-card, .product-grid-item")
        products: list[Product] = []
        seen: set[str] = set()

        for item in items:
            link_el = item.select_one('a[href*="/p/"], a[href*="/c/"]')
            href = (link_el.get("href") if link_el else "") or ""
            href = href.split("?")[0]
            if not href or href in seen:
                continue

            title_el = item.select_one("[data-testid='product-title'], .product-title, .product-name")
            title = title_el.get_text(" ", strip=True) if title_el else ""
            if not title or len(title) <= 5:
                continue

            price_el = item.select_one("[data-testid='product-price'], .price, .product-price")
            price = ""
            if price_el:
                price_match = re.search(r"\$?([\d,]+\.?\d*)", price_el.get_text(" ", strip=True))
                if price_match:
                    price = price_match.group(1).replace(",", "")

            img = item.select_one("img")
            image = img.get("src") or img.get("data-src") or "" if img else ""

            products.append(
                Product(
                    source="lowes",
                    url=urljoin("https://www.lowes.com", href),
                    title=title[:200],
                    price=price,
                    images=[image] if image else [],
                )
            )
            seen.add(href)

        return products

    def _extract_kohls_search(self, html: str) -> list[Product]:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

        soup = BeautifulSoup(html, "html.parser")
        items = soup.select("[data-testid='product-card'], .product-card, .product-block")
        products: list[Product] = []
        seen: set[str] = set()

        for item in items:
            link_el = item.select_one('a[href*="/p/"], a[href*="/product/"]')
            href = (link_el.get("href") if link_el else "") or ""
            href = href.split("?")[0]
            if not href or href in seen:
                continue

            title_el = item.select_one("[data-testid='product-title'], .product-title, .product-name, h3")
            title = title_el.get_text(" ", strip=True) if title_el else ""
            if not title or len(title) <= 5:
                continue

            price_el = item.select_one("[data-testid='product-price'], .price, .product-price")
            price = ""
            if price_el:
                price_match = re.search(r"\$?([\d,]+\.?\d*)", price_el.get_text(" ", strip=True))
                if price_match:
                    price = price_match.group(1).replace(",", "")

            img = item.select_one("img")
            image = img.get("src") or img.get("data-src") or "" if img else ""

            products.append(
                Product(
                    source="kohls",
                    url=urljoin("https://www.kohls.com", href),
                    title=title[:200],
                    price=price,
                    images=[image] if image else [],
                )
            )
            seen.add(href)

        return products

    def _extract_michaels_search(self, html: str) -> list[Product]:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

        soup = BeautifulSoup(html, "html.parser")
        items = soup.select("[data-testid='product-card'], .product-card, .product-grid-item")
        products: list[Product] = []
        seen: set[str] = set()

        for item in items:
            link_el = item.select_one('a[href*="/p/"], a[href*="/product/"]')
            href = (link_el.get("href") if link_el else "") or ""
            href = href.split("?")[0]
            if not href or href in seen:
                continue

            title_el = item.select_one("[data-testid='product-title'], .product-title, .product-name, h3")
            title = title_el.get_text(" ", strip=True) if title_el else ""
            if not title or len(title) <= 5:
                continue

            price_el = item.select_one("[data-testid='product-price'], .price, .product-price")
            price = ""
            if price_el:
                price_match = re.search(r"\$?([\d,]+\.?\d*)", price_el.get_text(" ", strip=True))
                if price_match:
                    price = price_match.group(1).replace(",", "")

            img = item.select_one("img")
            image = img.get("src") or img.get("data-src") or "" if img else ""

            products.append(
                Product(
                    source="michaels",
                    url=urljoin("https://www.michaels.com", href),
                    title=title[:200],
                    price=price,
                    images=[image] if image else [],
                )
            )
            seen.add(href)

        return products

    def _extract_qvc_search(self, html: str) -> list[Product]:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

        soup = BeautifulSoup(html, "html.parser")
        items = soup.select("[data-testid='product-card'], .product-card, .product-item")
        products: list[Product] = []
        seen: set[str] = set()

        for item in items:
            link_el = item.select_one('a[href*="/p/"], a[href*="/product/"]')
            href = (link_el.get("href") if link_el else "") or ""
            href = href.split("?")[0]
            if not href or href in seen:
                continue

            title_el = item.select_one("[data-testid='product-title'], .product-title, .product-name, h3")
            title = title_el.get_text(" ", strip=True) if title_el else ""
            if not title or len(title) <= 5:
                continue

            price_el = item.select_one("[data-testid='product-price'], .price, .product-price")
            price = ""
            if price_el:
                price_match = re.search(r"\$?([\d,]+\.?\d*)", price_el.get_text(" ", strip=True))
                if price_match:
                    price = price_match.group(1).replace(",", "")

            img = item.select_one("img")
            image = img.get("src") or img.get("data-src") or "" if img else ""

            products.append(
                Product(
                    source="qvc",
                    url=urljoin("https://www.qvc.com", href),
                    title=title[:200],
                    price=price,
                    images=[image] if image else [],
                )
            )
            seen.add(href)

        return products

    def _extract_bestbuy_search(self, html: str) -> list[Product]:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

        soup = BeautifulSoup(html, "html.parser")
        items = soup.select("[data-testid='product-card'], .sku-item, .product-item")
        products: list[Product] = []
        seen: set[str] = set()

        for item in items:
            link_el = item.select_one('a[href*="/p/"], a[href*="/sku/"]')
            href = (link_el.get("href") if link_el else "") or ""
            href = href.split("?")[0]
            if not href or href in seen:
                continue

            title_el = item.select_one("[data-testid='product-title'], .sku-title, .product-title, h3")
            title = title_el.get_text(" ", strip=True) if title_el else ""
            if not title or len(title) <= 5:
                continue

            price_el = item.select_one("[data-testid='product-price'], .price, .sku-price")
            price = ""
            if price_el:
                price_match = re.search(r"\$?([\d,]+\.?\d*)", price_el.get_text(" ", strip=True))
                if price_match:
                    price = price_match.group(1).replace(",", "")

            img = item.select_one("img")
            image = img.get("src") or img.get("data-src") or "" if img else ""

            products.append(
                Product(
                    source="bestbuy",
                    url=urljoin("https://www.bestbuy.com", href),
                    title=title[:200],
                    price=price,
                    images=[image] if image else [],
                )
            )
            seen.add(href)

        return products

    def _extract_costco_search(self, html: str) -> list[Product]:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

        soup = BeautifulSoup(html, "html.parser")
        items = soup.select("[data-testid='product-card'], .product-card, .product-tile")
        products: list[Product] = []
        seen: set[str] = set()

        for item in items:
            link_el = item.select_one('a[href*="/p/"], a[href*="/product/"]')
            href = (link_el.get("href") if link_el else "") or ""
            href = href.split("?")[0]
            if not href or href in seen:
                continue

            title_el = item.select_one("[data-testid='product-title'], .product-title, .description, h3")
            title = title_el.get_text(" ", strip=True) if title_el else ""
            if not title or len(title) <= 5:
                continue

            price_el = item.select_one("[data-testid='product-price'], .price, .product-price")
            price = ""
            if price_el:
                price_match = re.search(r"\$?([\d,]+\.?\d*)", price_el.get_text(" ", strip=True))
                if price_match:
                    price = price_match.group(1).replace(",", "")

            img = item.select_one("img")
            image = img.get("src") or img.get("data-src") or "" if img else ""

            products.append(
                Product(
                    source="costco",
                    url=urljoin("https://www.costco.com", href),
                    title=title[:200],
                    price=price,
                    images=[image] if image else [],
                )
            )
            seen.add(href)

        return products

    def _extract_samsclub_search(self, html: str) -> list[Product]:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

        soup = BeautifulSoup(html, "html.parser")
        items = soup.select("[data-testid='product-card'], .product-card, .product-tile")
        products: list[Product] = []
        seen: set[str] = set()

        for item in items:
            link_el = item.select_one('a[href*="/p/"], a[href*="/pd/"]')
            href = (link_el.get("href") if link_el else "") or ""
            href = href.split("?")[0]
            if not href or href in seen:
                continue

            title_el = item.select_one("[data-testid='product-title'], .product-title, .title, h3")
            title = title_el.get_text(" ", strip=True) if title_el else ""
            if not title or len(title) <= 5:
                continue

            price_el = item.select_one("[data-testid='product-price'], .price, .product-price")
            price = ""
            if price_el:
                price_match = re.search(r"\$?([\d,]+\.?\d*)", price_el.get_text(" ", strip=True))
                if price_match:
                    price = price_match.group(1).replace(",", "")

            img = item.select_one("img")
            image = img.get("src") or img.get("data-src") or "" if img else ""

            products.append(
                Product(
                    source="samsclub",
                    url=urljoin("https://www.samsclub.com", href),
                    title=title[:200],
                    price=price,
                    images=[image] if image else [],
                )
            )
            seen.add(href)

        return products

    def _extract_menards_search(self, html: str) -> list[Product]:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

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

    def _extract_mercadolibre_search(self, html: str) -> list[Product]:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

        soup = BeautifulSoup(html, "html.parser")
        items = soup.select("[data-testid='product-card'], .ui-card, .product-item")
        products: list[Product] = []
        seen: set[str] = set()

        for item in items:
            link_el = item.select_one('a[href*="/MLM-"], a[href*="/p/"]')
            href = (link_el.get("href") if link_el else "") or ""
            href = href.split("?")[0]
            if not href or href in seen:
                continue

            title_el = item.select_one("[data-testid='product-title'], .ui-card__title, .product-title, h3")
            title = title_el.get_text(" ", strip=True) if title_el else ""
            if not title or len(title) <= 5:
                continue

            price_el = item.select_one("[data-testid='product-price'], .price, .ui-card__price")
            price = ""
            if price_el:
                price_text = price_el.get_text(" ", strip=True)
                price_match = re.search(r"[\d,]+\.?\d*", price_text)
                if price_match:
                    price = price_match.group().replace(",", "")

            img = item.select_one("img")
            image = img.get("src") or img.get("data-src") or "" if img else ""

            products.append(
                Product(
                    source="mercadolibre",
                    url=urljoin("https://www.mercadolibre.com.mx", href),
                    title=title[:200],
                    price=price,
                    images=[image] if image else [],
                )
            )
            seen.add(href)

        return products


import structlog
log = structlog.get_logger()
