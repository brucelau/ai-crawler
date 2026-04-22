import re
from typing import Any

import structlog

from ai_crawler.core.extraction.base import ExtractionStrategy
from ai_crawler.models.product import Product

log = structlog.get_logger()


class DetailPageExtraction(ExtractionStrategy):
    name = "detail_page"
    method = "generic_detail"

    PRICE_PATTERNS = [
        r"[$€£¥₹]\s?[\d,]+(?:\.\d{2})?",
        r"[\d,]+(?:\.\d{2})?\s?[$€£¥₹]",
        r"USD\s?[\d,]+(?:\.\d{2})?",
        r"Price:\s*[$€£¥₹]?\s?[\d,]+(?:\.\d{2})?",
    ]

    RATING_PATTERNS = [
        r"([0-5](?:\.\d)?)\s*(?:out of\s*)?5?\s*(?:star|star[s]?)",
        r"rating[:\s]+([0-5](?:\.\d)?)",
        r"([0-5](?:\.\d)?)\s*/\s*5",
    ]

    REVIEW_COUNT_PATTERNS = [
        r"([\d,]+)\s*(?:customer\s*)?reviews?",
        r"([\d,]+)\s*ratings?",
        r"([\d,]+)\s*people.*said",
    ]

    def __init__(self):
        super().__init__(name=self.name, method=self.method)

    def extract(self, page: Any, html: str, url: str) -> list[Product]:
        if not html:
            return []

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        source = self._infer_source(url)

        title = self._extract_title(soup)
        price = self._extract_price(soup, html)
        currency = self._extract_currency(html, price)
        rating = self._extract_rating(soup, html)
        review_count = self._extract_review_count(soup, html)
        description = self._extract_description(soup)
        images = self._extract_images(soup, html)
        availability = self._extract_availability(soup)
        brand = self._extract_brand(soup)

        if not title:
            return []

        product = Product(
            source=source,
            url=url,
            title=title[:500] if title else "",
            price=price,
            currency=currency,
            rating=rating,
            review_count=review_count,
            brand=brand,
            description=description[:2000] if description else "",
            images=images,
            availability=availability,
        )

        return [product]

    def _infer_source(self, url: str) -> str:
        from ai_crawler.utils.site import infer_site_from_url_or_empty

        return infer_site_from_url_or_empty(url)

    def _extract_title(self, soup) -> str:
        candidates = []

        itemprop_name = soup.find(attrs={"itemprop": "name"})
        if itemprop_name:
            text = itemprop_name.get_text(" ", strip=True)
            if text:
                candidates.append(("itemprop", text))

        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            candidates.append(("og:title", og_title["content"]))

        h1 = soup.find("h1")
        if h1:
            text = h1.get_text(" ", strip=True)
            if text and len(text) > 5:
                candidates.append(("h1", text))

        title_tag = soup.find("title")
        if title_tag:
            text = title_tag.get_text(" ", strip=True)
            if text and len(text) > 5:
                candidates.append(("title", text))

        title = soup.find("meta", attrs={"name": "title"})
        if title and title.get("content"):
            candidates.append(("meta:title", title["content"]))

        best = self._pick_best_title(candidates)
        if best:
            return best

        return ""

    def _pick_best_title(self, candidates: list[tuple[str, str]]) -> str:
        if not candidates:
            return ""

        for source_type, text in candidates:
            text = text.strip()
            if not text or len(text) < 10:
                continue
            if any(skip in text.lower() for skip in ["sign in", "login", "cart", "checkout", "404", "error"]):
                continue
            return text

        return candidates[0][1] if candidates else ""

    def _extract_price(self, soup, html: str) -> str:
        candidates = []

        itemprop_price = soup.find(attrs={"itemprop": "price"})
        if itemprop_price:
            content = itemprop_price.get("content") or itemprop_price.get_text(" ", strip=True)
            if content:
                candidates.append(("itemprop", content))

        meta_price = soup.find("meta", attrs={"itemprop": "price", "content": True})
        if meta_price:
            candidates.append(("meta", meta_price["content"]))

        price_el = soup.find(attrs={"data-testid": re.compile(r"price", re.I)})
        if price_el:
            text = price_el.get_text(" ", strip=True)
            if text:
                candidates.append(("data-testid", text))

        class_price = soup.find(class_=re.compile(r"price[-_]?(?:current|actual|sale)", re.I))
        if class_price:
            text = class_price.get_text(" ", strip=True)
            if text:
                candidates.append(("class", text))

        for pattern in self.PRICE_PATTERNS:
            match = re.search(pattern, html, re.I)
            if match:
                candidates.append(("regex", match.group()))

        if candidates:
            return self._normalize_price(candidates[-1][1])

        return ""

    def _normalize_price(self, text: str) -> str:
        text = re.sub(r"[^\d.,]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _extract_currency(self, html: str, price: str) -> str:
        if not price:
            return ""

        currency_map = {
            "$": "USD",
            "€": "EUR",
            "£": "GBP",
            "¥": "JPY",
            "₹": "INR",
            "A$": "AUD",
            "C$": "CAD",
        }

        for symbol, code in currency_map.items():
            if symbol in html:
                return code

        if "USD" in html.upper():
            return "USD"
        if "EUR" in html.upper():
            return "EUR"
        if "GBP" in html.upper():
            return "GBP"

        return ""

    def _extract_rating(self, soup, html: str) -> float:
        itemprop_rating = soup.find(attrs={"itemprop": "ratingValue"})
        if itemprop_rating:
            try:
                return float(itemprop_rating.get("content") or itemprop_rating.get_text())
            except (ValueError, TypeError):
                pass

        meta_rating = soup.find("meta", attrs={"itemprop": "ratingValue", "content": True})
        if meta_rating:
            try:
                return float(meta_rating["content"])
            except (ValueError, TypeError):
                pass

        for pattern in self.RATING_PATTERNS:
            match = re.search(pattern, html, re.I)
            if match:
                try:
                    return float(match.group(1))
                except (ValueError, TypeError):
                    pass

        return 0.0

    def _extract_review_count(self, soup, html: str) -> int:
        itemprop_reviews = soup.find(attrs={"itemprop": "reviewCount"})
        if itemprop_reviews:
            try:
                text = itemprop_reviews.get("content") or itemprop_reviews.get_text()
                return int(re.sub(r"[^\d]", "", text))
            except (ValueError, TypeError):
                pass

        meta_review_count = soup.find("meta", attrs={"itemprop": "reviewCount", "content": True})
        if meta_review_count:
            try:
                return int(re.sub(r"[^\d]", "", meta_review_count["content"]))
            except (ValueError, TypeError):
                pass

        for pattern in self.REVIEW_COUNT_PATTERNS:
            match = re.search(pattern, html, re.I)
            if match:
                try:
                    return int(match.group(1).replace(",", ""))
                except (ValueError, TypeError):
                    pass

        return 0

    def _extract_description(self, soup) -> str:
        itemprop_desc = soup.find(attrs={"itemprop": "description"})
        if itemprop_desc:
            return itemprop_desc.get_text("\n", strip=True)

        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            return og_desc["content"]

        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            return meta_desc["content"]

        desc_el = soup.find("div", class_=re.compile(r"description", re.I))
        if desc_el:
            return desc_el.get_text("\n", strip=True)

        return ""

    def _extract_images(self, soup, html: str) -> list[str]:
        images = []

        itemprop_image = soup.find(attrs={"itemprop": "image"})
        if itemprop_image:
            src = itemprop_image.get("src") or itemprop_image.get("content")
            if src:
                images.append(src)

        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            images.append(og_image["content"])

        product_images = soup.find_all("img", attrs={"itemprop": "image"})
        for img in product_images:
            src = img.get("src") or img.get("data-src")
            if src and src not in images:
                images.append(src)

        main_image = soup.find("img", class_=re.compile(r"main|primary|hero|product", re.I))
        if main_image:
            src = main_image.get("src") or main_image.get("data-src")
            if src and src not in images:
                images.append(src)

        return images[:5]

    def _extract_availability(self, soup) -> str:
        itemprop_avail = soup.find(attrs={"itemprop": "availability"})
        if itemprop_avail:
            href = itemprop_avail.get("href", "")
            if "InStock" in href or "instock" in href.lower():
                return "InStock"
            if "OutOfStock" in href or "outofstock" in href.lower():
                return "OutOfStock"
            if "PreOrder" in href or "preorder" in href.lower():
                return "PreOrder"

        avail_text = soup.find(string=re.compile(r"(?:in stock|out of stock|pre-order|available|sold out)", re.I))
        if avail_text:
            text = avail_text.lower()
            if "in stock" in text or "available" in text:
                return "InStock"
            if "out of stock" in text or "sold out" in text:
                return "OutOfStock"
            if "pre-order" in text:
                return "PreOrder"

        return ""

    def _extract_brand(self, soup) -> str:
        itemprop_brand = soup.find(attrs={"itemprop": "brand"})
        if itemprop_brand:
            return itemprop_brand.get_text(" ", strip=True)

        meta_brand = soup.find("meta", property="og:brand")
        if meta_brand and meta_brand.get("content"):
            return meta_brand["content"]

        brand_el = soup.find(class_=re.compile(r"brand|manufacturer", re.I))
        if brand_el:
            return brand_el.get_text(" ", strip=True)

        return ""
