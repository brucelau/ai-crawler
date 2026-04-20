from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from ai_crawler.config.sites import (
    PATTERNS,
    SITE_TIER_DEFAULTS,
    TIER_CONFIGS,
    URL_PATTERNS,
)
from ai_crawler.core.types import (
    CrawlStrategy,
    PagePattern,
    ProxyType,
    RenderType,
    TierSystem,
)


def get_site_tier(site: str, page_pattern: PagePattern) -> int:
    if site in SITE_TIER_DEFAULTS:
        site_tiers = SITE_TIER_DEFAULTS[site]
        if page_pattern in site_tiers:
            return site_tiers[page_pattern]
        if PagePattern.UNKNOWN in site_tiers:
            return site_tiers[PagePattern.UNKNOWN]
    return 1


class PatternMatcher:
    @classmethod
    def detect(cls, site: str, url: str) -> PagePattern:
        site_patterns = PATTERNS.get(site, {})
        for pattern_enum, regex_list in site_patterns.items():
            for regex in regex_list:
                if re.search(regex, url, re.IGNORECASE):
                    return pattern_enum
        return PagePattern.UNKNOWN


@dataclass
class CrawlTask:
    url: str
    site: str
    page_pattern: PagePattern = PagePattern.UNKNOWN
    strategies: list[CrawlStrategy] = field(default_factory=list)
    current_index: int = 0
    fail_count: int = 0
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    query: str | None = None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def create(cls, url: str, site: str, use_auto_strategies: bool = True) -> "CrawlTask":
        pattern = PatternMatcher.detect(site, url)

        if use_auto_strategies:
            from ai_crawler.core.engine.strategy_generator import StrategyGenerator
            from ai_crawler.core.engine.policy_engine import PolicyEngine, PolicyStatsStore

            stats_store = PolicyStatsStore()
            engine = PolicyEngine(stats_store)
            strategies = StrategyGenerator.get_optimal_strategies(
                site, pattern.value, engine, top_n=10
            )
            if not strategies:
                strategies = [CrawlStrategy()]
        else:
            strategies = URL_PATTERNS.get(site, {}).get(
                pattern, URL_PATTERNS.get(site, {}).get(PagePattern.UNKNOWN, [])
            )
            if not strategies:
                strategies = [CrawlStrategy()]

        return cls(url=url, site=site, page_pattern=pattern, strategies=list(strategies))

    @classmethod
    def create_from_tier(
        cls,
        url: str,
        site: str,
        page_pattern: PagePattern | None = None,
        query: str | None = None,
    ) -> "CrawlTask":
        if page_pattern is None:
            page_pattern = PatternMatcher.detect(site, url)
        start_tier = 1  # 完全交给 PolicyEngine 决定，不使用 site.yaml tier 建议
        strategies = CrawlStrategy.get_tier_strategies(start_tier, end_tier=9)
        return cls(
            url=url,
            site=site,
            page_pattern=page_pattern,
            strategies=strategies,
            query=query,
            metadata={"start_tier": start_tier, "page_pattern": page_pattern.value},
        )

    def current_strategy(self) -> CrawlStrategy | None:
        if self.current_index >= len(self.strategies):
            return None
        return self.strategies[self.current_index]

    def exhausted(self) -> bool:
        return self.current_index >= len(self.strategies)

    def advance(self) -> None:
        self.current_index += 1

    def add_strategy_front(self, strategy: CrawlStrategy) -> None:
        if self.current_index > 0:
            self.strategies.insert(self.current_index, strategy)
        else:
            self.strategies.insert(0, strategy)

    def add_strategy_next(self, strategy: CrawlStrategy) -> None:
        insert_at = min(self.current_index + 1, len(self.strategies))
        self.strategies.insert(insert_at, strategy)

    def reset(self) -> None:
        self.current_index = 0
        self.fail_count = 0

    def attempt_summary(self) -> dict:
        return {
            "task_id": self.task_id,
            "url": self.url,
            "site": self.site,
            "pattern": self.page_pattern.value,
            "current_index": self.current_index,
            "total_strategies": len(self.strategies),
            "fail_count": self.fail_count,
        }
