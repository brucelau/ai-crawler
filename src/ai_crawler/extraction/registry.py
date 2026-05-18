"""提取策略注册表"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_crawler.extraction.base import ExtractionStrategy

from ai_crawler.extraction.extractors.axtree import AXTreeExtractor
from ai_crawler.extraction.extractors.api_intercept import APIInterceptExtractor
from ai_crawler.extraction.extractors.bs_css import BSExtractor
from ai_crawler.extraction.generic.detail_page import DetailPageExtraction
from ai_crawler.extraction.extractors.json_ld import JSONLDExtractor
from ai_crawler.extraction.extractors.js_eval import JSEvaluateExtractor

STRATEGY_REGISTRY: dict[str, type["ExtractionStrategy"]] = {
    "json_ld": JSONLDExtractor,
    "js_eval": JSEvaluateExtractor,
    "api_intercept": APIInterceptExtractor,
    "axtree": AXTreeExtractor,
    "bs_css": BSExtractor,
    "detail_page": DetailPageExtraction,
}


def create_strategy(name: str) -> "ExtractionStrategy":
    cls = STRATEGY_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown extraction strategy: {name}")
    if name == "api_intercept":
        return cls(name="api_intercept", method="api_intercept")
    return cls()


def list_strategies() -> list[str]:
    return list(STRATEGY_REGISTRY.keys())