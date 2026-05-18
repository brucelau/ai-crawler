from __future__ import annotations

import json
import re
import time
from typing import Optional

from bs4 import BeautifulSoup

from ai_crawler.core.config import config
from ai_crawler.extraction import build_axtree_selector_sample
from ai_crawler.extraction.templates.template_store import template_store
from ai_crawler.extraction.analysis.validators import validate_selector
from ai_crawler.core.types import Product


class LLMExtractor:
    _instance: Optional["LLMExtractor"] = None
    _cache: dict[str, dict] = {}
    _cache_ttl: float = 86400.0

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._dspy_extractor = None

    def _get_dspy_extractor(self):
        if not config.has_llm():
            return None
        if self._dspy_extractor is None:
            from ai_crawler.llm.dspy_model import SelectorExtractor

            self._dspy_extractor = SelectorExtractor()
        return self._dspy_extractor

    def _cache_key(self, site: str, page_type: str) -> str:
        return f"{site}:{page_type}"

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"\s+", " ", (value or "")).strip()

    def _looks_like_valid_search_product(
        self,
        site: str,
        title: str,
        link: str,
        price: str,
        source_url: str,
    ) -> bool:
        title = self._normalize_text(title)
        lowered = title.lower()
        generic_titles = {
            "type",
            "shop",
            "search",
            "result",
            "products",
            "target",
            "amazon",
        }
        if not title:
            return False
        if lowered in generic_titles:
            return False
        if len(title) < 8:
            return False
        if len(title.split()) < 2 and not price:
            return False
        if link and link == source_url:
            return False
        if site == "target" and link and "/p/" not in link and "/A-" not in link:
            return False
        if site == "amazon" and link and "/dp/" not in link and "/gp/" not in link:
            return False
        return True

    def _is_cache_valid(self, site: str, page_type: str) -> bool:
        key = self._cache_key(site, page_type)
        if key not in self._cache:
            return False
        cached_time = self._cache[key].get("_cached_at", 0)
        return (time.time() - cached_time) < self._cache_ttl

    def _generate_selectors(
        self,
        site: str,
        page_type: str,
        html_sample: str,
        semantic_sample: str = "",
    ) -> dict:
        extractor = self._get_dspy_extractor()
        if not extractor:
            return self._default_selectors(site, page_type)

        try:
            raw_result = extractor(
                site=site,
                page_type=page_type,
                html_sample=html_sample[:8000],
                semantic_sample=semantic_sample[:2000],
            )
            result = validate_selector(raw_result.__dict__)
            selectors = result.model_dump()
            selectors["_cached_at"] = time.time()
            return selectors
        except Exception:
            return self._default_selectors(site, page_type)

    def _default_selectors(self, site: str, page_type: str = "search") -> dict:
        defaults = {
            "amazon": {
                "site": "amazon",
                "page_type": page_type,
                "list_container": "ul.s-result-list > li",
                "product_selector": "[data-asin]",
                "title_selector": "span.a-text-normal, h2 a span",
                "price_selector": "span.a-price-whole",
                "price_fraction_selector": "span.a-price-fraction",
                "image_selector": "img.s-image",
                "rating_selector": "i.a-icon-star-small .a-icon-alt",
                "review_count_selector": "span.a-size-small.a-link-normal",
                "link_selector": "h2 a",
                "product_id_attribute": "data-asin",
            },
            "walmart": {
                "site": "walmart",
                "page_type": page_type,
                "list_container": "div.search-result-gridview-item",
                "product_selector": "div.search-result-gridview-item",
                "title_selector": "div.search-result-product-title a span",
                "price_selector": "span.price-main-block span",
                "image_selector": "img.search-result-image",
                "rating_selector": "span.search-result-star-rating",
                "review_count_selector": "span.search-result-review-count",
                "link_selector": "div.search-result-product-title a",
            },
            "default": {
                "site": site,
                "page_type": page_type,
                "list_container": "li.product, div.product-item, div[itemtype*='Product']",
                "product_selector": "li.product, div.product-item",
                "title_selector": "h2, h3, .product-title, .title",
                "price_selector": ".price, .product-price, [class*='price']",
                "image_selector": "img[class*='product'], img[class*='thumbnail']",
                "rating_selector": ".rating, .stars, [class*='star']",
                "review_count_selector": ".reviews, .review-count",
                "link_selector": "a[href*='product'], a.product-link",
            },
        }
        result = defaults.get(site, defaults["default"]).copy()
        result["_cached_at"] = time.time()
        return result

    def get_selectors(
        self,
        site: str,
        page_type: str,
        html_sample: str = "",
        semantic_sample: str = "",
        force_regenerate: bool = False,
    ) -> dict:
        key = self._cache_key(site, page_type)
        if self._is_cache_valid(site, page_type) and not force_regenerate:
            cached = self._cache[key].copy()
            del cached["_cached_at"]
            return cached

        if not force_regenerate and html_sample:
            template = template_store.load(site, page_type)
            if template:
                self._cache[key] = template
                cached = template.copy()
                if "_cached_at" in cached:
                    del cached["_cached_at"]
                return cached

        selectors = self._generate_selectors(site, page_type, html_sample, semantic_sample)
        template_store.save(site, page_type, selectors)
        self._cache[key] = selectors
        cached = selectors.copy()
        if "_cached_at" in cached:
            del cached["_cached_at"]
        return cached

    def extract(
        self, html: str, site: str, page_type: str, url: str, force_regenerate: bool = False
    ) -> list[Product]:
        return self.extract_with_page(
            html,
            page=None,
            site=site,
            page_type=page_type,
            url=url,
            force_regenerate=force_regenerate,
        )

    def extract_with_page(
        self,
        html: str,
        page: any,
        site: str,
        page_type: str,
        url: str,
        force_regenerate: bool = False,
    ) -> list[Product]:
        semantic_sample = ""
        if page is not None:
            semantic_sample = build_axtree_selector_sample(page, url, page_type)
        selectors = self.get_selectors(
            site,
            page_type,
            html[:50000],
            semantic_sample=semantic_sample,
            force_regenerate=force_regenerate,
        )
        soup = BeautifulSoup(html, "html.parser")

        products = []
        list_container = selectors.get("list_container")
        product_selector = selectors.get("product_selector")

        items = soup.select(list_container) if list_container else []
        if not items and product_selector:
            items = soup.select(product_selector)
        if not items:
            items = soup.select("li, div")

        for item in items[:20]:
            try:
                title_el = item.select_one(selectors.get("title_selector", "h2, h3"))
                title = title_el.get_text(strip=True) if title_el else ""

                price = ""
                price_el = item.select_one(selectors.get("price_selector", ".price"))
                if price_el:
                    price = price_el.get_text(strip=True)
                    frac_sel = selectors.get("price_fraction_selector")
                    if frac_sel:
                        frac_el = item.select_one(frac_sel)
                        if frac_el:
                            price = f"{price}.{frac_el.get_text(strip=True)}"

                rating = 0.0
                rating_el = item.select_one(selectors.get("rating_selector", ".rating"))
                if rating_el:
                    rating_text = rating_el.get_text(strip=True)
                    match = re.search(r"([0-9.]+)", rating_text)
                    if match:
                        rating = float(match.group(1))

                review_count = 0
                review_el = item.select_one(
                    selectors.get("review_count_selector", ".reviews, .review-count")
                )
                if review_el:
                    review_text = review_el.get_text(strip=True)
                    match = re.search(r"([0-9,]+)", review_text)
                    if match:
                        review_count = int(match.group(1).replace(",", ""))

                image = ""
                img_el = item.select_one(selectors.get("image_selector", "img"))
                if img_el:
                    image = img_el.get("src") or img_el.get("data-src", "")

                link = ""
                link_el = item.select_one(selectors.get("link_selector", "a"))
                if link_el:
                    href = link_el.get("href", "")
                    if href:
                        from urllib.parse import urljoin

                        link = urljoin(url, href)

                product_id = ""
                prod_id_attr = selectors.get("product_id_attribute")
                if prod_id_attr:
                    product_id = item.get(prod_id_attr, "")

                if title or price:
                    final_url = link or url
                    if page_type == "search" and not self._looks_like_valid_search_product(
                        site, title, final_url, price, url
                    ):
                        continue
                    products.append(
                        Product(
                            source=site,
                            url=final_url,
                            title=title,
                            price=price,
                            rating=rating,
                            review_count=review_count,
                            images=[image] if image else [],
                            asin=product_id,
                        )
                    )
            except Exception:
                continue

        deduped: list[Product] = []
        seen_keys: set[tuple[str, str]] = set()
        for product in products:
            key = (self._normalize_text(product.title).lower(), product.url)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(product)

        return deduped


llm_extractor = LLMExtractor()


def extract_with_llm(
    html: str, site: str, page_type: str, url: str, force_regenerate: bool = False
) -> list[Product]:
    return llm_extractor.extract(html, site, page_type, url, force_regenerate=force_regenerate)


def extract_with_llm_page(
    html: str,
    page: any,
    site: str,
    page_type: str,
    url: str,
    force_regenerate: bool = False,
) -> list[Product]:
    return llm_extractor.extract_with_page(
        html,
        page,
        site,
        page_type,
        url,
        force_regenerate=force_regenerate,
    )
