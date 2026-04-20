from dataclasses import dataclass
import structlog
from typing import Any

from ai_crawler.models.product import Product

log = structlog.get_logger()


@dataclass
class ExtractionResult:
    products: list[Product]
    strategy: str
    method: str
    outcome: str = "success"


class ExtractionStrategy:
    name: str
    method: str

    def extract(self, page: Any, html: str, url: str) -> list[Product]:
        raise NotImplementedError


class GenericCSSFallback(ExtractionStrategy):
    name = "generic_css_fallback"
    method = "beautifulsoup"

    def extract(self, page: Any, html: str, url: str) -> list[Product]:
        from bs4 import BeautifulSoup

        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        source = self._infer_source(url)
        products: list[Product] = []
        seen_titles: set[str] = set()

        generic_selectors = [
            "article",
            'li[data-item-id]',
            'li[class*="product"]',
            'div[class*="product"][class*="item"]',
            "[itemtype*='Product']",
            '[data-testid*="product"]',
            'div[class*="search"][class*="result"]',
            'li[class*="catalogue"]',
        ]

        for selector in generic_selectors:
            for item in soup.select(selector):
                title = ""
                title_el = item.select_one("h2, h3, [class*='title'], [class*='name']")
                if title_el:
                    title = title_el.get_text(" ", strip=True)
                if not title:
                    link_el = item.select_one("a[href*='/p/'], a[href*='/ip/'], a[href*='/product/']")
                    if link_el:
                        title = link_el.get_text(" ", strip=True)
                if not title or len(title) <= 5:
                    continue
                if title in seen_titles:
                    continue
                seen_titles.add(title)

                price = ""
                price_el = item.select_one("[class*='price'], .a-price, [itemprop='price']")
                if price_el:
                    price_text = price_el.get_text(" ", strip=True)
                    import re
                    price_match = re.search(r"[\d,]+\.?\d*", price_text)
                    if price_match:
                        price = price_match.group()

                image = ""
                img = item.select_one("img")
                if img:
                    image = img.get("src") or img.get("data-src") or ""

                link = ""
                link_el = item.select_one("a[href]")
                if link_el:
                    link = link_el.get("href", "")

                products.append(
                    Product(
                        source=source,
                        url=link,
                        title=title[:200],
                        price=price,
                        images=[image] if image else [],
                    )
                )

                if len(products) >= 20:
                    break

            if products:
                break

        return products

    def _infer_source(self, url: str) -> str:
        from ai_crawler.utils.site import infer_site_from_url
        return infer_site_from_url(url)


class ExtractorChain:
    def __init__(self, strategies: list[tuple[str, int, ExtractionStrategy]]):
        self.strategies = strategies

    def extract(
        self, page: Any, html: str, url: str, page_type: str = "unknown"
    ) -> ExtractionResult:
        strategies = self.strategies
        if page_type == "search":
            strategies = self._reorder_for_search(strategies)
        results: list[ExtractionResult] = []
        for name, min_needed, strategy in strategies:
            try:
                products = strategy.extract(page, html, url)
                if len(products) >= min_needed:
                    results.append(
                        ExtractionResult(
                            products=products,
                            strategy=name,
                            method=strategy.method,
                        )
                    )
            except Exception:
                log.debug("extraction_strategy_failed", strategy_name=name)
                continue
        if results:
            return max(results, key=lambda r: len(r.products))

        try:
            fallback = GenericCSSFallback()
            products = fallback.extract(page, html, url)
            if products:
                return ExtractionResult(
                    products=products,
                    strategy="generic_css_fallback",
                    method="beautifulsoup",
                )
        except Exception:
            log.debug("generic_css_fallback_failed")

        return ExtractionResult(products=[], strategy="none", method="none")

    def _reorder_for_search(
        self, strategies: list[tuple[str, int, ExtractionStrategy]]
    ) -> list[tuple[str, int, ExtractionStrategy]]:
        priority = {"js_eval": 0, "json_ld": 1, "api_intercept": 2, "bs_css": 3, "axtree": 4}
        return sorted(strategies, key=lambda s: priority.get(s[0], 99))
