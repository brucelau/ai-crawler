from ai_crawler.core.types import (
    CrawlStrategy,
    CrawlTask,
    ProxyType,
    RenderType,
    PagePattern,
    TierSystem,
    TIER_CONFIGS,
)
from ai_crawler.config.sites import URL_PATTERNS, SITE_TIER_DEFAULTS, PATTERNS
from ai_crawler.browser.fetching import Fetcher
from ai_crawler.core.runner import CrawlRunner
from ai_crawler.core.engine.proxying import ProxyProvider
from ai_crawler.core.engine.results import CrawlResult

try:
    from ai_crawler.core.llm import (
        DSPyScheduler,
        DSPyTrainer,
        StrategySelector,
        ThresholdOptimizer,
        URLDiscoverer,
        HumanBehaviorGenerator,
        load_traces,
        train_dspy_model,
    )
except ModuleNotFoundError:  # optional engine dependencies
    DSPyScheduler = None
    DSPyTrainer = None
    StrategySelector = None
    ThresholdOptimizer = None
    URLDiscoverer = None
    HumanBehaviorGenerator = None
    load_traces = None
    train_dspy_model = None
from ai_crawler.core.extraction import (
    BlockResult,
    HumanBehaviorResult,
    SelectorResult,
    ThresholdResult,
    URLDiscoveryResult,
    validate_block,
    validate_human_behavior,
    validate_selector,
    validate_threshold,
    validate_url_discovery,
)
from ai_crawler.core.engine import (
    AntiBotHandler,
    AntiBotTrace,
    BlockDetector,
    BlockType,
    Queue,
    SiteMemory,
    StrategyAttempt,
    TraceStore,
)

__all__ = [
    "AntiBotHandler",
    "AntiBotTrace",
    "BlockDetector",
    "BlockResult",
    "BlockType",
    "Queue",
    "CrawlResult",
    "CrawlRunner",
    "CrawlStrategy",
    "CrawlTask",
    "DSPyScheduler",
    "DSPyTrainer",
    "Fetcher",
    "HumanBehaviorGenerator",
    "HumanBehaviorResult",
    "PagePattern",
    "ProxyProvider",
    "ProxyType",
    "RenderType",
    "SelectorResult",
    "SiteMemory",
    "SITE_TIER_DEFAULTS",
    "StrategyAttempt",
    "StrategySelector",
    "ThresholdOptimizer",
    "TIER_CONFIGS",
    "TierSystem",
    "TraceStore",
    "URLDiscoveryResult",
    "URL_PATTERNS",
    "URLDiscoverer",
    "load_traces",
    "train_dspy_model",
    "validate_block",
    "validate_human_behavior",
    "validate_selector",
    "validate_threshold",
    "validate_url_discovery",
]
