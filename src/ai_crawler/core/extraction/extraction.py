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
    ExtractorChain,
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

SITE_EXTRACTION_CHAINS: dict = {}


def _build_default_chains():
    global SITE_EXTRACTION_CHAINS
    SITE_EXTRACTION_CHAINS = {
        "ebay": ExtractorChain(
            _insert_axtree_before_bs_css([
                ("json_ld", 5, JSONLDExtraction()),
                ("js_eval", 5, JSEvaluateExtraction()),
                ("api_intercept", 10, APIInterceptExtraction()),
                ("bs_css", 3, BSExtraction()),
            ])
        ),
        "target": ExtractorChain(
            _insert_axtree_before_bs_css([
                ("json_ld", 3, JSONLDExtraction()),
                ("js_eval", 5, JSEvaluateExtraction()),
                ("api_intercept", 10, APIInterceptExtraction()),
                ("bs_css", 3, BSExtraction()),
            ])
        ),
        "amazon": ExtractorChain(
            _insert_axtree_before_bs_css([
                ("js_eval", 5, JSEvaluateExtraction()),
                ("bs_css", 3, BSExtraction()),
            ])
        ),
        "walmart": ExtractorChain(
            _insert_axtree_before_bs_css([
                ("json_ld", 3, JSONLDExtraction()),
                ("js_eval", 5, JSEvaluateExtraction()),
                ("api_intercept", 10, APIInterceptExtraction()),
                ("bs_css", 3, BSExtraction()),
            ])
        ),
        "lowes": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "homedepot": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "acehardware": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "menards": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "wayfair": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "michaels": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "temu": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "etsy": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "bestbuy": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "costco": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "qvc": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "kohls": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "mercadolibre": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "walmartmexico": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "intexcorp": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "meijer": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "fivebelow": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "samsclub": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "bunnings": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "dollargeneral": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "action": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "academy": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "wowsports": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "coppel": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "aosom": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "familydollar": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
        "costway": ExtractorChain([
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]),
    }


def _insert_axtree_before_bs_css(
    strategies: list,
) -> list:
    if any(name == "axtree" for name, _, _ in strategies):
        return strategies

    enhanced: list = []
    inserted = False
    for name, min_needed, strategy in strategies:
        if name == "bs_css" and not inserted:
            enhanced.append(("axtree", 3, AXTreeExtraction()))
            inserted = True
        enhanced.append((name, min_needed, strategy))

    if not inserted:
        enhanced.append(("axtree", 3, AXTreeExtraction()))
    return enhanced


_build_default_chains()
