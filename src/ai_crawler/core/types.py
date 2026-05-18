"""Shared types — enums, dataclasses, errors, and constants used across all packages."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from ai_crawler.crawl.results import CrawlResult as CoreCrawlResult


# ═══════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════

class ProxyType(Enum):
    THORDATA_US = "thordata_us"
    THORDATA_US_CITY = "thordata_us_city"
    THORDATA_ANY = "thordata_any"
    THORDATA_DEDICATED = "thordata_dedicated"


class RenderType(Enum):
    NONE = "none"
    OPENCLI = "opencli"
    CLOUDSCRAPER = "cloudscraper"
    LIGHTPAND = "lightpand"
    PLAYWRIGHT = "playwright"
    CAMOUFOX = "camoufox"
    CLOAKBROWSER = "cloakbrowser"
    CLOUDERA = "cloudflare_uc"
    SELENIUMBASE = "seleniumbase"
    KAMELEO = "kameleo"


class TierSystem(Enum):
    TIER_0 = 0  # OpenCLI - user's logged-in Chrome, fastest path
    TIER_1 = 1  # curl_cffi - fastest, simplest
    TIER_2 = 2  # cloudscraper - simple anti-bot
    TIER_3 = 3  # [DEPRECATED] Lightpanda - removed (no pip package)
    TIER_4 = 4  # Playwright - full browser
    TIER_5 = 5  # Camoufox - fingerprint-aware Firefox
    TIER_6 = 6  # undetected-chromedriver - Cloudflare specialist
    TIER_7 = 7  # SeleniumBase - maximum stealth
    TIER_8 = 8  # CloakBrowser - C++ patched Chromium, ultimate stealth
    TIER_9 = 9  # [DEPRECATED] Kameleo - fingerprint browser, highest tier


class PagePattern(Enum):
    SEARCH = "search"
    DETAIL = "detail"
    SELLER = "seller"
    REVIEW = "review"
    HOME = "home"
    UNKNOWN = "unknown"



# ═══════════════════════════════════════════════════════════════════
# CrawlPolicy
# ═══════════════════════════════════════════════════════════════════

@dataclass
class CrawlPolicy:
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



# ═══════════════════════════════════════════════════════════════════
# StrategyAttempt
# ═══════════════════════════════════════════════════════════════════

@dataclass
class StrategyAttempt:
    task_id: str
    url: str
    site: str
    page_pattern: str
    strategy: CrawlPolicy
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
        strategy = CrawlPolicy(
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


# ═══════════════════════════════════════════════════════════════════
# SiteMemory
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SiteMemory:
    site: str
    page_pattern: str
    successful_strategies: list[CrawlPolicy] = field(default_factory=list)
    attempt_log: list[StrategyAttempt] = field(default_factory=list)
    llm_tier_cache: dict[str, int] = field(default_factory=dict)
    extraction_method_stats: dict[str, dict[str, int]] = field(default_factory=dict)
    # Smart strategy selection
    waf_type: str = ""
    min_working_level: int | None = None
    last_success_level: int | None = None
    try_downward: bool = False

    def record_success(self, strategy: CrawlPolicy):
        if strategy not in self.successful_strategies:
            self.successful_strategies.insert(0, strategy)
        level = getattr(strategy, 'tier', 0)
        if self.min_working_level is None or level < self.min_working_level:
            self.min_working_level = level
        self.last_success_level = level
        self.try_downward = True

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
            "waf_type": self.waf_type,
            "min_working_level": self.min_working_level,
            "last_success_level": self.last_success_level,
            "try_downward": self.try_downward,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SiteMemory":
        strategies = [
            CrawlPolicy(
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
            waf_type=data.get("waf_type", ""),
            min_working_level=data.get("min_working_level"),
            last_success_level=data.get("last_success_level"),
            try_downward=data.get("try_downward", False),
        )


# ═══════════════════════════════════════════════════════════════════
# CrawlTask
# ═══════════════════════════════════════════════════════════════════

@dataclass
class CrawlTask:
    url: str
    site: str
    page_pattern: PagePattern = PagePattern.UNKNOWN
    strategy: CrawlPolicy | None = None
    current_level: int = 0
    fail_count: int = 0
    attempt_count: int = 0
    max_attempts: int = 8
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    query: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    site_memory: SiteMemory | None = None

    def attempt_summary(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "url": self.url,
            "site": self.site,
            "pattern": self.page_pattern.value,
            "current_level": self.current_level,
            "fail_count": self.fail_count,
            "attempt_count": self.attempt_count,
        }


# ═══════════════════════════════════════════════════════════════════
# Product (from models/product.py)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Product:
    source: str = ""
    url: str = ""
    title: str = ""
    price: str = ""
    currency: str = ""
    rating: float = 0.0
    review_count: int = 0
    brand: str = ""
    description: str = ""
    images: list = None
    availability: str = ""
    asin: str = ""
    seller: str = ""
    shipping: str = ""
    category: str = ""
    extracted_at: str = ""

    def __post_init__(self):
        if self.images is None:
            self.images = []

    def to_dict(self) -> dict:
        return asdict(self)


def product_to_item(product: Product) -> dict:
    return product.to_dict()


# ═══════════════════════════════════════════════════════════════════
# Errors (from spider/engine/errors.py)
# ═══════════════════════════════════════════════════════════════════

class CrawlerError(Exception):
    pass


class FetchError(CrawlerError):
    pass


class BlockDetectedError(FetchError):
    def __init__(self, block_type: str, message: str = ""):
        self.block_type = block_type
        super().__init__(message or block_type)


class ProxyError(CrawlerError):
    pass


class ProxyAuthError(ProxyError):
    pass


class BrowserError(CrawlerError):
    pass


class BrowserLaunchError(BrowserError):
    pass


class ExtractionError(CrawlerError):
    pass


class CaptchaError(CrawlerError):
    pass


class CaptchaSolveError(CaptchaError):
    pass


# ═══════════════════════════════════════════════════════════════════
# Scoring constants (from spider/engine/constants.py)
# ═══════════════════════════════════════════════════════════════════

RENDER_COST = {
    RenderType.NONE.value: 1,
    RenderType.CLOUDSCRAPER.value: 2,
    RenderType.PLAYWRIGHT.value: 4,
    RenderType.CAMOUFOX.value: 5,
    RenderType.CLOUDERA.value: 6,
    RenderType.SELENIUMBASE.value: 7,
    RenderType.CLOAKBROWSER.value: 8,
    RenderType.KAMELEO.value: 9,
}

UC_SEARCH_ALLOWLIST = {"amazon", "walmart"}

ANTI_BOT_PENALTIES = {
    ("vendors", "browser_error"): 25,
    ("mechanisms", "proxy_transport_error"): 20,
    ("mechanisms", "browser_transport_error"): 15,
    ("mechanisms", "js_challenge"): 10,
    ("mechanisms", "captcha_gate"): 12,
    ("mechanisms", "bot_score_gate"): 10,
}

SCORE_WEIGHTS = {
    "success": 100,
    "yield": 3,
    "order_base": 20,
    "order_decay": 2,
    "latency_per_sec": 0.8,
    "http_timeout_rate": 20,
    "captcha_rate": 25,
    "cloudflare_rate": 15,
    "bot_rate": 15,
    "cost_multiplier": 2,
    "instability_threshold": 3,
    "instability_penalty": 10,
}

CONTEXTUAL_BONUSES = {
    (PagePattern.SEARCH.value, RenderType.CAMOUFOX.value): 12,
    (PagePattern.SEARCH.value, RenderType.CLOAKBROWSER.value): 14,
    (PagePattern.SEARCH.value, RenderType.SELENIUMBASE.value): 6,
    (PagePattern.SEARCH.value, RenderType.CLOUDERA.value): 35,
}

CONTEXTUAL_BONUSES_SUCCESS = {
    (PagePattern.SEARCH.value, RenderType.CAMOUFOX.value): 8,
    (PagePattern.SEARCH.value, RenderType.CLOAKBROWSER.value): 10,
    (PagePattern.SEARCH.value, RenderType.SELENIUMBASE.value): 4,
}

CLOAKBROWSER_AMAZON_TARGET_BONUS = 8
CLOUDERA_NON_ALLOWLIST_PENALTY = 10


# ═══════════════════════════════════════════════════════════════════
# MemoryStore (from spider/runtime/crawl.py — kept here for now,
# moves to storage/site_memory.py in Phase 5)
# ═══════════════════════════════════════════════════════════════════

class MemoryStore:
    def __init__(self, storage_dir: str = "site_memory", backend: Any = None):
        from ai_crawler.storage.backend import LocalStorageBackend

        self.storage_dir = storage_dir
        self.backend = backend or LocalStorageBackend()
        self.backend.makedirs(storage_dir)

    def _site_file(self, site: str) -> str:
        safe_name = site.replace("/", "_").replace("\\", "_")
        return f"{self.storage_dir}/{safe_name}.json"

    def save(self, memories: dict[tuple[str, str], SiteMemory]) -> None:
        for (site, page_pattern), memory in memories.items():
            if memory.successful_strategies or memory.attempt_log:
                file_path = self._site_file(site)
                data = json.dumps(memory.to_dict())
                self.backend.write_text(file_path, data)

    def load(self, site: str) -> dict[tuple[str, str], SiteMemory]:
        memories: dict[tuple[str, str], SiteMemory] = {}
        file_path = self._site_file(site)
        if self.backend.exists(file_path):
            try:
                data = json.loads(self.backend.read_text(file_path))
                key = (data["site"], data["page_pattern"])
                memories[key] = SiteMemory.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                pass
        return memories


# ═══════════════════════════════════════════════════════════════════
# API model types (from api/models.py)
# ═══════════════════════════════════════════════════════════════════

TaskGoal = Literal["search", "detail", "category", "reviews"]
SignalType = Literal[
    "ok",
    "retryable_network",
    "soft_block",
    "hard_block",
    "extraction_failure",
    "non_recoverable",
]


@dataclass(slots=True)
class RuntimeTask:
    id: str
    site: str
    url: str
    goal: TaskGoal
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    session_policy: str = "reuse_or_fresh"
    extraction_mode: str = "site_chain_then_llm"
    max_attempts: int = 5


@dataclass(slots=True)
class StrategyPlan:
    tier: int | None
    render_mode: str
    proxy_mode: str
    use_fingerprint: bool = True
    use_cookies: bool = True
    use_human_behavior: bool = False
    block_retryable: bool = True
    timeout_ms: int = 30000
    wait_selector: str | None = None
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_crawl_strategy(cls, strategy: CrawlPolicy | None) -> "StrategyPlan | None":
        if strategy is None:
            return None
        return cls(
            tier=getattr(strategy, "tier", None),
            render_mode=strategy.render.value,
            proxy_mode=strategy.proxy.value,
            use_fingerprint=strategy.change_ua,
            use_cookies=strategy.use_cookies,
            use_human_behavior=strategy.use_human_scroll,
            wait_selector=strategy.wait_selector,
            tags=[
                f"tier:{getattr(strategy, 'tier', 'unknown')}",
                f"render:{strategy.render.value}",
            ],
        )


@dataclass(slots=True)
class BrowserSession:
    id: str
    site: str
    proxy_id: str | None = None
    fingerprint_id: str | None = None
    storage_state_path: str | None = None
    context_metadata: dict[str, Any] = field(default_factory=dict)
    healthy: bool = True


@dataclass(slots=True)
class DetectionSignal:
    type: SignalType
    score: float = 1.0
    retryable: bool = True
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_core_result(cls, result: "CoreCrawlResult") -> "DetectionSignal":
        if result.success:
            return cls(type="ok", retryable=False, details={"block_type": result.block_type})

        block_type = str(result.block_type or "unknown")
        hard_blocks = {"captcha", "cloudflare", "http_403", "http_451", "bot_detected"}
        retryable_network = {"http_timeout", "http_429"}
        non_recoverable = {"unsupported_site", "invalid_url"}

        if block_type in non_recoverable:
            return cls(type="non_recoverable", retryable=False, details={"block_type": block_type})
        if block_type in retryable_network:
            return cls(type="retryable_network", details={"block_type": block_type})
        if block_type in hard_blocks:
            return cls(type="hard_block", details={"block_type": block_type})
        if block_type == "empty_content":
            return cls(type="extraction_failure", details={"block_type": block_type})
        return cls(type="soft_block", details={"block_type": block_type})


@dataclass(slots=True)
class ExtractionOutcome:
    success: bool
    items: list[Product] = field(default_factory=list)
    extractor: str = ""
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_core_result(cls, result: "CoreCrawlResult") -> "ExtractionOutcome":
        products = list(result.products or [])
        return cls(
            success=bool(result.success and products),
            items=products,
            extractor=result.extraction_strategy or "site_chain",
            confidence=1.0 if products else 0.0,
            warnings=[] if products else ["No products extracted"],
        )


@dataclass(slots=True)
class RuntimeTaskResult:
    task: RuntimeTask
    success: bool
    final_url: str | None = None
    status_code: int | None = None
    strategy: StrategyPlan | None = None
    session: BrowserSession | None = None
    signal: DetectionSignal | None = None
    extraction: ExtractionOutcome | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    core_result: "CoreCrawlResult | None" = None

    @property
    def products(self) -> list[Product]:
        return self.extraction.items if self.extraction else []

    @classmethod
    def from_core_result(cls, task: RuntimeTask, result: "CoreCrawlResult") -> "RuntimeTaskResult":
        session = BrowserSession(id=task.id, site=task.site)
        return cls(
            task=task,
            success=result.success,
            final_url=result.task.url,
            status_code=None,
            strategy=StrategyPlan.from_crawl_strategy(result.strategy),
            session=session,
            signal=DetectionSignal.from_core_result(result),
            extraction=ExtractionOutcome.from_core_result(result),
            artifacts={
                "html_size": len(result.html or ""),
                "extraction_strategy": result.extraction_strategy or "none",
                "extraction_method": result.extraction_method or "none",
                "axtree_hit": bool((result.extraction_metadata or {}).get("axtree_hit", False)),
                "anti_bot_fingerprint": (result.extraction_metadata or {}).get(
                    "anti_bot_fingerprint",
                    result.anti_bot_fingerprint if hasattr(result, "anti_bot_fingerprint") else {},
                ),
            },
            error=result.error or None,
            core_result=result,
        )


@dataclass(slots=True)
class RuntimeBatchResult:
    products: list[Product]
    task_results: list[RuntimeTaskResult]
    stats: dict[str, Any]
    output_files: list[str]
    traces_file: str


__all__ = [
    "ProxyType",
    "RenderType",
    "TierSystem",
    "PagePattern",
    "CrawlPolicy",
    "StrategyAttempt",
    "SiteMemory",
    "CrawlTask",
    "Product",
    "product_to_item",
    "CrawlerError",
    "FetchError",
    "BlockDetectedError",
    "ProxyError",
    "ProxyAuthError",
    "BrowserError",
    "BrowserLaunchError",
    "ExtractionError",
    "CaptchaError",
    "CaptchaSolveError",
    "RENDER_COST",
    "MemoryStore",
    "TaskGoal",
    "SignalType",
    "RuntimeTask",
    "StrategyPlan",
    "BrowserSession",
    "DetectionSignal",
    "ExtractionOutcome",
    "RuntimeTaskResult",
    "RuntimeBatchResult",
]
