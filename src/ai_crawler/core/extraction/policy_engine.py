"""解析策略引擎 - 决定提取策略的执行顺序"""
from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from ai_crawler.core.extraction.page_analyzer import PageFeatures
    from ai_crawler.core.types import SiteMemory, MemoryStore

log = structlog.get_logger()


class ExtractionPolicyEngine:
    """基于页面特征和历史数据，动态决定提取策略顺序"""

    DEFAULT_PRIORITY = {
        "json_ld": 1.0,
        "api_intercept": 2.0,
        "js_eval": 3.0,
        "axtree": 4.0,
        "bs_css": 5.0,
    }

    DETAIL_PAGE_PRIORITY = {
        "detail_page": 1.0,
        "json_ld": 2.0,
        "axtree": 3.0,
        "bs_css": 4.0,
        "js_eval": 5.0,
        "api_intercept": 6.0,
    }

    def __init__(self, memory_store: MemoryStore | None = None):
        self.memory_store = memory_store
        self._memory: dict[str, "SiteMemory"] = {}
        self._order_cache: dict[str, list[str]] = {}

    def get_order(
        self,
        site: str,
        page_type: str,
        features: "PageFeatures",
    ) -> list[str]:
        cache_key = f"{site}:{page_type}"
        if cache_key in self._order_cache:
            return self._order_cache[cache_key]

        if page_type == "detail":
            scores = dict(self.DETAIL_PAGE_PRIORITY)
        else:
            scores = dict(self.DEFAULT_PRIORITY)
            scores = self._apply_feature_boosts(scores, features)

        memory = self._get_memory(site, page_type)
        if memory:
            scores = self._apply_historical_boosts(scores, memory)

        order = sorted(scores.keys(), key=lambda k: scores[k])
        self._order_cache[cache_key] = order
        return order

    def record(
        self,
        site: str,
        page_type: str,
        method: str,
        product_count: int,
        success: bool,
    ) -> None:
        memory = self._get_memory(site, page_type)
        if memory is None:
            return
        outcome = "success" if success and product_count >= 3 else "partial"
        memory.record_extraction_quality(method, outcome, product_count)
        self._invalidate_cache(site, page_type)

    def get_best_method(self, site: str, page_type: str) -> str | None:
        memory = self._get_memory(site, page_type)
        if not memory:
            return None
        return memory.get_best_extraction_method()

    def get_stats(self, site: str, page_type: str) -> dict | None:
        memory = self._get_memory(site, page_type)
        if not memory:
            return None
        return dict(memory.extraction_method_stats)

    def _apply_feature_boosts(
        self,
        scores: dict[str, float],
        features: "PageFeatures",
    ) -> dict[str, float]:
        if features.has_json_ld:
            scores["json_ld"] *= 0.1
        if features.has_spa_signature:
            scores["js_eval"] *= 0.3
            scores["axtree"] *= 0.5
        if features.has_api_signatures:
            scores["api_intercept"] *= 0.2
        if features.is_infinite_scroll:
            scores["js_eval"] *= 0.3
        return scores

    def _apply_historical_boosts(
        self,
        scores: dict[str, float],
        memory: "SiteMemory",
    ) -> dict[str, float]:
        best = memory.get_best_extraction_method()
        if best and best in scores:
            scores[best] *= 0.5
        return scores

    def _get_memory(self, site: str, page_type: str) -> "SiteMemory | None":
        from ai_crawler.core.types import SiteMemory

        key = f"{site}:{page_type}"
        if key not in self._memory:
            if self.memory_store:
                memories = self.memory_store.load(site)
                self._memory[key] = memories.get(key)
            else:
                self._memory[key] = SiteMemory(site=site, page_pattern=page_type)
        return self._memory[key]

    def _invalidate_cache(self, site: str, page_type: str) -> None:
        key = f"{site}:{page_type}"
        self._order_cache.pop(key, None)

    def flush(self) -> None:
        if self.memory_store:
            self.memory_store.save(self._memory)
