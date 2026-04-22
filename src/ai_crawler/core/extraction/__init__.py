from ai_crawler.core.extraction.base import (
    ExtractionResult,
    ExtractionStrategy,
    GenericCSSFallback,
)
from ai_crawler.core.extraction.engine import ExtractionEngine, ExtractionOutcomeType, ExtractionDecision
from ai_crawler.core.extraction.json_ld import JSONLDExtraction
from ai_crawler.core.extraction.js_eval import JSEvaluateExtraction
from ai_crawler.core.extraction.api_intercept import APIInterceptExtraction
from ai_crawler.core.extraction.bs_css import BSExtraction
from ai_crawler.core.extraction.axtree import AXTreeExtraction
from ai_crawler.core.extraction.extraction import (
    build_axtree_semantic_confirmation,
    build_axtree_selector_sample,
)
from ai_crawler.core.extraction.page_analyzer import PageAnalyzer, PageFeatures
from ai_crawler.core.extraction.policy_engine import ExtractionPolicyEngine
from ai_crawler.core.extraction.registry import STRATEGY_REGISTRY, create_strategy, list_strategies
from ai_crawler.core.extraction.template_store import TemplateStore, template_store
from ai_crawler.core.extraction.validators import (
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

__all__ = [
    "APIInterceptExtraction",
    "AXTreeExtraction",
    "BlockResult",
    "BSExtraction",
    "create_strategy",
    "ExtractionDecision",
    "ExtractionEngine",
    "ExtractionOutcomeType",
    "ExtractionResult",
    "ExtractionPolicyEngine",
    "ExtractionStrategy",
    "GenericCSSFallback",
    "HumanBehaviorResult",
    "JSONLDExtraction",
    "JSEvaluateExtraction",
    "list_strategies",
    "PageAnalyzer",
    "PageFeatures",
    "SelectorResult",
    "STRATEGY_REGISTRY",
    "build_axtree_semantic_confirmation",
    "build_axtree_selector_sample",
    "TemplateStore",
    "template_store",
    "ThresholdResult",
    "URLDiscoveryResult",
    "validate_block",
    "validate_human_behavior",
    "validate_selector",
    "validate_threshold",
    "validate_url_discovery",
]
