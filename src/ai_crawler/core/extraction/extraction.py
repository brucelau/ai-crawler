"""Backward compatibility - re-exports from split modules.

This file exists for backward compatibility.
New code should import directly from the split modules:
- ai_crawler.core.extraction.base
- ai_crawler.core.extraction.json_ld
- ai_crawler.core.extraction.js_eval
- ai_crawler.core.extraction.api_intercept
- ai_crawler.core.extraction.bs_css
- ai_crawler.core.extraction.axtree
"""

from typing import Any

from ai_crawler.core.extraction.base import (
    ExtractionResult,
    ExtractionStrategy,
    GenericCSSFallback,
)
from ai_crawler.core.extraction.json_ld import JSONLDExtraction
from ai_crawler.core.extraction.js_eval import JSEvaluateExtraction
from ai_crawler.core.extraction.api_intercept import APIInterceptExtraction
from ai_crawler.core.extraction.bs_css import BSExtraction
from ai_crawler.core.extraction.axtree import AXTreeExtraction

from ai_crawler.utils.site import infer_site_from_url, infer_site_from_url_or_empty


def build_axtree_semantic_confirmation(
    page: Any, url: str, page_pattern: str = "unknown"
) -> dict | None:
    return AXTreeExtraction().build_semantic_confirmation(page, url, page_pattern)


def build_axtree_selector_sample(
    page: Any,
    url: str,
    page_pattern: str = "unknown",
    max_products: int = 4,
    max_chars: int = 2000,
) -> str:
    return AXTreeExtraction().build_selector_semantic_sample(
        page,
        url,
        page_pattern=page_pattern,
        max_products=max_products,
        max_chars=max_chars,
    )
