from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ai_crawler.core.extraction.base import ExtractionResult
from ai_crawler.models.product import Product


@dataclass
class ExtractionTemplate:
    site: str
    page_type: str
    css_selector: str | None = None
    js_selector: str | None = None
    is_valid: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    success_count: int = 0
    failure_count: int = 0

    def extract(self, page: Any, html: str, url: str) -> ExtractionResult:
        if self.css_selector:
            result = self._extract_with_css(html, url)
            if result.products:
                self.success_count += 1
                return result

        if self.js_selector:
            result = self._extract_with_js(page, url)
            if result.products:
                self.success_count += 1
                return result

        self.failure_count += 1
        self.is_valid = False
        return ExtractionResult(products=[], strategy=self.site, method="template")

    def _extract_with_css(self, html: str, url: str) -> ExtractionResult:
        from bs4 import BeautifulSoup

        if not html or not self.css_selector:
            return ExtractionResult(products=[], strategy=self.site, method="template_css")

        soup = BeautifulSoup(html, "html.parser")
        products: list[Product] = []
        seen_titles: set[str] = set()

        for item in soup.select(self.css_selector):
            title_el = item.select_one("h2, h3, [class*='title'], [class*='name'], a[href]")
            title = ""
            if title_el:
                title = title_el.get_text(" ", strip=True)
            if not title or len(title) <= 5:
                continue
            if title in seen_titles:
                continue
            seen_titles.add(title)

            price_el = item.select_one("[class*='price'], .a-price, [itemprop='price']")
            price = ""
            if price_el:
                import re
                price_text = price_el.get_text(" ", strip=True)
                price_match = re.search(r"[\d,]+\.?\d*", price_text)
                if price_match:
                    price = price_match.group()

            img_el = item.select_one("img")
            image = ""
            if img_el:
                image = img.get("src") or img.get("data-src") or ""

            link_el = item.select_one("a[href]")
            link = ""
            if link_el:
                link = str(link_el.get("href", "")) or ""

            products.append(
                Product(
                    source=self.site,
                    url=link,
                    title=title[:200],
                    price=price,
                    images=[image] if image else [],
                )
            )

            if len(products) >= 20:
                break

        return ExtractionResult(
            products=products,
            strategy=self.site,
            method="template_css",
        )

    def _extract_with_js(self, page: Any, url: str) -> ExtractionResult:
        if not page or not self.js_selector:
            return ExtractionResult(products=[], strategy=self.site, method="template_js")

        try:
            script = f"""
            (() => {{
                const items = document.querySelectorAll('{self.js_selector}');
                return Array.from(items).map(el => {{
                    const titleEl = el.querySelector('span, div, h2, h3, a') || el;
                    const title = titleEl ? titleEl.textContent.trim() : '';
                    const priceEl = el.querySelector('[class*="price"]');
                    const price = priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '';
                    const imgEl = el.querySelector('img');
                    const image = imgEl ? (imgEl.src || imgEl.dataset.src || '') : '';
                    const linkEl = el.querySelector('a[href]');
                    const link = linkEl ? linkEl.href : '';
                    return {{ title, price, image, link }};
                }}).filter(p => p.title && p.title.length > 5);
            }})()
            """
            items = page.evaluate(script)
            if not items:
                return ExtractionResult(products=[], strategy=self.site, method="template_js")

            products = [
                Product(
                    source=self.site,
                    url=item.get("link", ""),
                    title=item.get("title", "")[:200],
                    price=item.get("price", ""),
                    images=[item.get("image", "")] if item.get("image") else [],
                )
                for item in items
            ]
            return ExtractionResult(products=products, strategy=self.site, method="template_js")
        except Exception:
            return ExtractionResult(products=[], strategy=self.site, method="template_js")


# 模板存储
_extraction_templates: dict[tuple[str, str], ExtractionTemplate] = {}


def get_template(site: str, page_type: str) -> ExtractionTemplate | None:
    return _extraction_templates.get((site, page_type))


def save_template(template: ExtractionTemplate) -> None:
    _extraction_templates[(template.site, template.page_type)] = template


def invalidate_template(site: str, page_type: str) -> None:
    key = (site, page_type)
    if key in _extraction_templates:
        _extraction_templates[key].is_valid = False


def clear_templates() -> None:
    _extraction_templates.clear()


def llm_generate_template(
    site: str,
    page_type: str,
    html: str,
    products: list[Product],
    page: Any = None,
) -> ExtractionTemplate | None:
    """用 LLM 生成提取模板"""
    try:
        from ai_crawler.core.llm.llm_extractor import llm_extractor

        semantic_sample = ""
        if page:
            from ai_crawler.core.extraction import build_axtree_selector_sample

            semantic_sample = build_axtree_selector_sample(page, "", page_type)

        selectors = llm_extractor.get_selectors(
            site=site,
            page_type=page_type,
            html_sample=html[:50000],
            semantic_sample=semantic_sample,
            force_regenerate=True,
        )

        css_selector = selectors.get("product_selector") or selectors.get("list_container")

        return ExtractionTemplate(
            site=site,
            page_type=page_type,
            css_selector=css_selector,
            js_selector=None,
            is_valid=True,
        )
    except Exception:
        return None
