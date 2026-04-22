from __future__ import annotations

import json
import os
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Sequence # 导入 Any, Sequence

import structlog

log = structlog.get_logger()


class ProxyType(Enum):
    THORDATA_US = "thordata_us"
    THORDATA_US_CITY = "thordata_us_city"
    THORDATA_ANY = "thordata_any"
    THORDATA_DEDICATED = "thordata_dedicated"


class RenderType(Enum):
    NONE = "none"
    CLOUDSCRAPER = "cloudscraper"
    LIGHTPAND = "lightpand"
    PLAYWRIGHT = "playwright"
    CAMOUFOX = "camoufox"
    CLOAKBROWSER = "cloakbrowser"
    CLOUDERA = "cloudflare_uc"
    SELENIUMBASE = "seleniumbase"
    KAMELEO = "kameleo"


class TierSystem(Enum):
    TIER_1 = 1  # curl_cffi - fastest, simplest
    TIER_2 = 2  # cloudscraper - simple anti-bot
    TIER_3 = 3  # Lightpanda - lightweight browser, sub-100ms startup, JS rendering
    TIER_4 = 4  # Playwright - full browser
    TIER_5 = 5  # Camoufox - fingerprint-aware Firefox
    TIER_6 = 6  # undetected-chromedriver - Cloudflare specialist
    TIER_7 = 7  # SeleniumBase - maximum stealth
    TIER_8 = 8  # CloakBrowser - C++ patched Chromium, ultimate stealth
    TIER_9 = 9  # [DEPRECATED] Kameleo - fingerprint browser, highest tier


DEPRECATED_TIERS = {9}


TIER_CONFIGS: dict[int, dict] = {
    1: {
        "render": RenderType.NONE,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (2, 5),
        "use_human_scroll": False,
        "change_ua": False,
        "use_cookies": False,
    },
    2: {
        "render": RenderType.CLOUDSCRAPER,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (3, 6),
        "use_human_scroll": False,
        "change_ua": False,
        "use_cookies": True,
    },
    3: {
        "render": RenderType.LIGHTPAND,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (2, 5),
        "use_human_scroll": True,
        "change_ua": False,
        "use_cookies": False,
    },
    4: {
        "render": RenderType.PLAYWRIGHT,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (3, 8),
        "use_human_scroll": True,
        "change_ua": False,
        "use_cookies": False,
    },
    5: {
        "render": RenderType.CAMOUFOX,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (3, 8),
        "use_human_scroll": True,
        "change_ua": True,
        "use_cookies": True,
    },
    6: {
        "render": RenderType.CLOUDERA,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (5, 10),
        "use_human_scroll": True,
        "change_ua": True,
        "use_cookies": True,
    },
    7: {
        "render": RenderType.SELENIUMBASE,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (5, 10),
        "use_human_scroll": True,
        "change_ua": True,
        "use_cookies": True,
    },
    8: {
        "render": RenderType.CLOAKBROWSER,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (5, 10),
        "use_human_scroll": True,
        "change_ua": True,
        "use_cookies": True,
    },
    9: {
        "render": RenderType.KAMELEO,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (8, 15),
        "use_human_scroll": True,
        "change_ua": True,
        "use_cookies": True,
    },
}


class PagePattern(Enum):
    SEARCH = "search"
    DETAIL = "detail"
    SELLER = "seller"
    REVIEW = "review"
    HOME = "home"
    UNKNOWN = "unknown"


@dataclass
class CrawlStrategy:
    tier: int = 1
    proxy: ProxyType = ProxyType.THORDATA_DEDICATED
    render: RenderType = RenderType.NONE
    delay_before: tuple[float, float] = (0, 0)
    delay_after: tuple[float, float] = (3.0, 8.0)
    use_cookies: bool = False
    use_human_scroll: bool = False
    use_interactive_search: bool = False
    change_ua: bool = False
    wait_selector: str | None = None
    extra_wait: float = 0.0
    proxy_country: str | None = None
    proxy_city: str | None = None

    @classmethod
    def from_tier(cls, tier: int, **overrides) -> "CrawlStrategy":
        resolved_tier = tier if tier in TIER_CONFIGS else 1
        config = TIER_CONFIGS[resolved_tier]
        return cls(
            tier=resolved_tier,
            proxy=config["proxy"],
            render=config["render"],
            delay_after=config["delay_after"],
            use_human_scroll=config["use_human_scroll"],
            change_ua=config["change_ua"],
            use_cookies=config["use_cookies"],
            **overrides,
        )

    @classmethod
    def get_tier_strategies(cls, start_tier: int, end_tier: int = 9) -> list["CrawlStrategy"]:
        return [cls.from_tier(t) for t in range(start_tier, end_tier + 1)]


@dataclass
class StrategyAttempt:
    task_id: str
    url: str
    site: str
    page_pattern: str
    strategy: CrawlStrategy
    block_type: str
    response_snippet: str
    success: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "url": self.url,
            "site": self.site,
            "page_pattern": self.page_pattern,
            "strategy": {
                "tier": getattr(self.strategy, 'tier', 1),
                "render": self.strategy.render.value if hasattr(self.strategy, 'render') else "none",
                "proxy": self.strategy.proxy.value if hasattr(self.strategy, 'proxy') else "thordata_dedicated",
            },
            "block_type": self.block_type,
            "response_snippet": self.response_snippet,
            "success": self.success,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StrategyAttempt":
        strat_data = data.get("strategy", {})
        strategy = CrawlStrategy(
            tier=strat_data.get("tier", 1),
            render=RenderType(strat_data.get("render", "none")),
            proxy=ProxyType(strat_data.get("proxy", "thordata_dedicated")),
        )
        return cls(
            task_id=data["task_id"],
            url=data["url"],
            site=data["site"],
            page_pattern=data["page_pattern"],
            strategy=strategy,
            block_type=data["block_type"],
            response_snippet=data["response_snippet"],
            success=data["success"],
        )


@dataclass
class SiteMemory:
    site: str
    page_pattern: str
    successful_strategies: list[CrawlStrategy] = field(default_factory=list)
    attempt_log: list[StrategyAttempt] = field(default_factory=list)
    llm_tier_cache: dict[str, int] = field(default_factory=dict)
    extraction_method_stats: dict[str, dict[str, int]] = field(default_factory=dict)

    def record_success(self, strategy: CrawlStrategy):
        if strategy not in self.successful_strategies:
            self.successful_strategies.insert(0, strategy)

    def record_extraction_quality(self, method: str, outcome: str, product_count: int) -> None:
        if method not in self.extraction_method_stats:
            self.extraction_method_stats[method] = {"success": 0, "partial": 0, "empty": 0, "error": 0, "total_products": 0}
        stats = self.extraction_method_stats[method]
        if outcome == "success":
            stats["success"] += 1
            stats["total_products"] += product_count
        elif outcome == "partial_content":
            stats["partial"] += 1
            stats["total_products"] += product_count
        elif outcome == "empty_content":
            stats["empty"] += 1
        else:
            stats["error"] += 1

    def get_best_extraction_method(self) -> str | None:
        best_method = None
        best_score = -1
        for method, stats in self.extraction_method_stats.items():
            total = stats["success"] + stats["partial"]
            if total > best_score:
                best_score = total
                best_method = method
        return best_method

    def record_llm_tier(self, page_pattern: str, tier: int) -> None:
        self.llm_tier_cache[page_pattern] = tier

    def get_llm_tier(self, page_pattern: str) -> int | None:
        return self.llm_tier_cache.get(page_pattern)

    def recent_attempts(self, n: int = 5) -> list[StrategyAttempt]:
        return self.attempt_log[-n:]

    def get_failure_history_for_llm(self, page_pattern: str, n: int = 10) -> str:
        relevant_attempts = [
            a
            for a in self.attempt_log[-n:]
            if hasattr(a, "page_pattern") and a.page_pattern == page_pattern
        ]
        if not relevant_attempts:
            return ""
        history_parts = []
        for a in relevant_attempts[-5:]:
            history_parts.append(
                f"- Tier {getattr(a, 'strategy_tier', 1)}/{a.strategy_render}: "
                f"{a.block_type} (HTTP {getattr(a, 'status_code', 0)}, "
                f"WAF: {getattr(a, 'waf_detected', 'none')})"
            )
        return "\n".join(history_parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "site": self.site,
            "page_pattern": self.page_pattern,
            "successful_strategies": [
                {
                    "tier": getattr(s, 'tier', 1),
                    "render": s.render.value if hasattr(s, 'render') else "none",
                    "proxy": s.proxy.value if hasattr(s, 'proxy') else "thordata_dedicated",
                }
                for s in self.successful_strategies
            ],
            "attempt_log": [a.to_dict() for a in self.attempt_log],
            "llm_tier_cache": self.llm_tier_cache,
            "extraction_method_stats": self.extraction_method_stats,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SiteMemory":
        strategies = [
            CrawlStrategy(
                tier=s.get("tier", 1),
                render=RenderType(s.get("render", "none")),
                proxy=ProxyType(s.get("proxy", "thordata_dedicated")),
            )
            for s in data.get("successful_strategies", [])
        ]
        attempts = [StrategyAttempt.from_dict(a) for a in data.get("attempt_log", [])]
        return cls(
            site=data["site"],
            page_pattern=data["page_pattern"],
            successful_strategies=strategies,
            attempt_log=attempts,
            llm_tier_cache=data.get("llm_tier_cache", {}),
            extraction_method_stats=data.get("extraction_method_stats", {}),
        )


class MemoryStore:
    def __init__(self, storage_dir: str = "site_memory"):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

    def _site_file(self, site: str) -> str:
        safe_name = site.replace("/", "_").replace("\\", "_")
        return os.path.join(self.storage_dir, f"{safe_name}.json")

    def save(self, memories: dict[tuple[str, str], SiteMemory]) -> None:
        for (site, page_pattern), memory in memories.items():
            if memory.successful_strategies or memory.attempt_log:
                file_path = self._site_file(site)
                data = memory.to_dict()
                with open(file_path, "w") as f:
                    json.dump(data, f)

    def load(self, site: str) -> dict[tuple[str, str], SiteMemory]:
        memories: dict[tuple[str, str], SiteMemory] = {}
        file_path = self._site_file(site)
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                key = (data["site"], data["page_pattern"])
                memories[key] = SiteMemory.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                pass
        return memories


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
    metadata: dict[str, Any] = field(default_factory=dict)
    site_memory: SiteMemory | None = None # 新增 site_memory 属性

    @classmethod
    def create(cls, url: str, site: str, use_auto_strategies: bool = True) -> "CrawlTask":
        pattern = PagePattern.UNKNOWN # 临时替换为 UNKNOWN

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
            from ai_crawler.config.sites import URL_PATTERNS

            strategies = URL_PATTERNS.get(site, {}).get(
                pattern, URL_PATTERNS.get(site, {}).get(PagePattern.UNKNOWN, [])
            )
            if not strategies:
                strategies = [CrawlStrategy()]

        return cls(url=url, site=site, page_pattern=pattern, strategies=list(strategies))

    @classmethod
    def create_fast(cls, url: str, site: str) -> "CrawlTask":
        pattern = PagePattern.UNKNOWN # 临时替换为 UNKNOWN
        from ai_crawler.core.engine.strategy_generator import StrategyGenerator

        strategies = StrategyGenerator.get_default_strategies(site, pattern.value)
        task = cls(url=url, site=site, page_pattern=pattern, strategies=strategies[:10])
        task.metadata["strategy_pending"] = True
        return task

    @classmethod
    def create_from_tier(
        cls,
        url: str,
        site: str,
        page_pattern: PagePattern | None = None,
        query: str | None = None,
        metadata: dict[str, Any] | None = None,
        memory_store: SiteMemoryStore | None = None, # 接收 SiteMemoryStore
    ) -> "CrawlTask":
        
        # 确保 memory_store 变量被正确识别为 SiteMemoryStore 类型
        effective_memory_store: SiteMemoryStore | None = memory_store

        loaded_memories = effective_memory_store.load(site) if effective_memory_store else {}
        # 假设我们只关心特定 site 和 page_pattern 的 memory
        memory_key = (site, page_pattern.value if page_pattern else PagePattern.UNKNOWN.value)
        site_memory: SiteMemory | None = loaded_memories.get(memory_key)

        if page_pattern is None:
            page_pattern = PagePattern.UNKNOWN # 临时替换为 UNKNOWN
            if page_pattern is None:
                page_pattern = PagePattern.UNKNOWN


        start_tier = 1
        strategies = CrawlStrategy.get_tier_strategies(start_tier, end_tier=9)
        
        return cls(
            url=url,
            site=site,
            page_pattern=page_pattern,
            strategies=strategies,
            query=query,
            metadata=metadata or {},
            site_memory=site_memory,
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

    def attempt_summary(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "url": self.url,
            "site": self.site,
            "pattern": self.page_pattern.value,
            "current_index": self.current_index,
            "total_strategies": len(self.strategies),
            "fail_count": self.fail_count,
        }


__all__ = [
    "ProxyType",
    "RenderType",
    "TierSystem",
    "DEPRECATED_TIERS",
    "TIER_CONFIGS",
    "PagePattern",
    "CrawlStrategy",
    "StrategyAttempt",
    "SiteMemory",
    "SiteMemoryStore",
    "CrawlTask",
]
