from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from ai_crawler.core.engine.results import CrawlResult as CoreCrawlResult
from ai_crawler.core.types import CrawlStrategy
from ai_crawler.models.product import Product


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
    def from_crawl_strategy(cls, strategy: CrawlStrategy | None) -> "StrategyPlan | None":
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
    def from_core_result(cls, result: CoreCrawlResult) -> "DetectionSignal":
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
    def from_core_result(cls, result: CoreCrawlResult) -> "ExtractionOutcome":
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
    core_result: CoreCrawlResult | None = None

    @property
    def products(self) -> list[Product]:
        return self.extraction.items if self.extraction else []

    @classmethod
    def from_core_result(cls, task: RuntimeTask, result: CoreCrawlResult) -> "RuntimeTaskResult":
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
