"""提取策略注册表"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_crawler.core.extraction.base import ExtractionStrategy

from ai_crawler.core.extraction.axtree import AXTreeExtraction
from ai_crawler.core.extraction.api_intercept import APIInterceptExtraction
from ai_crawler.core.extraction.bs_css import BSExtraction
from ai_crawler.core.extraction.detail_page import DetailPageExtraction
from ai_crawler.core.extraction.json_ld import JSONLDExtraction
from ai_crawler.core.extraction.js_eval import JSEvaluateExtraction

STRATEGY_REGISTRY: dict[str, type["ExtractionStrategy"]] = {
    "json_ld": JSONLDExtraction,
    "js_eval": JSEvaluateExtraction,
    "api_intercept": APIInterceptExtraction,
    "axtree": AXTreeExtraction,
    "bs_css": BSExtraction,
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
