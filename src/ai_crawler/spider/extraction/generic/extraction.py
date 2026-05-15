"""Backward compatibility - re-exports from split modules.

This file exists for backward compatibility.
New code should import directly from the split modules:
- ai_crawler.spider.extraction.base
- ai_crawler.spider.extraction.extractors.json_ld
- ai_crawler.spider.extraction.extractors.js_eval
- ai_crawler.spider.extraction.extractors.api_intercept
- ai_crawler.spider.extraction.extractors.bs_css
- ai_crawler.spider.extraction.extractors.axtree
"""

from typing import Any

from ai_crawler.spider.extraction.base import (
    ExtractionResult,
    ExtractionStrategy,
    GenericCSSFallback,
)
from ai_crawler.spider.extraction.extractors.json_ld import JSONLDExtractor
from ai_crawler.spider.extraction.extractors.js_eval import JSEvaluateExtractor
from ai_crawler.spider.extraction.extractors.api_intercept import APIInterceptExtractor
from ai_crawler.spider.extraction.extractors.bs_css import BSExtractor
from ai_crawler.spider.extraction.extractors.axtree import AXTreeExtractor

from ai_crawler.config.sites import infer_site_from_url, infer_site_from_url_or_empty


def build_axtree_semantic_confirmation(
    page: Any, url: str, page_pattern: str = "unknown"
) -> dict | None:
    return AXTreeExtractor().build_semantic_confirmation(page, url, page_pattern)


def build_axtree_selector_sample(
    page: Any,
    url: str,
    page_pattern: str = "unknown",
    max_products: int = 4,
    max_chars: int = 2000,
) -> str:
    return AXTreeExtractor().build_selector_semantic_sample(
        page,
        url,
        page_pattern=page_pattern,
        max_products=max_products,
        max_chars=max_chars,
    )
