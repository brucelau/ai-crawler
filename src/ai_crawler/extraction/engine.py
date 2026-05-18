from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import structlog

from ai_crawler.extraction.base import ExtractionResult
from ai_crawler.extraction.analysis.page_analyzer import PageAnalyzer, PageFeatures
from ai_crawler.extraction.policy import ExtractionPolicyEngine
from ai_crawler.core.types import CrawlPolicy, CrawlTask
from ai_crawler.core.types import Product

log = structlog.get_logger()


class ExtractionOutcomeType(Enum):
    SUCCESS = "success"
    EMPTY_CONTENT = "empty_content"
    PARTIAL_CONTENT = "partial_content"
    EXTRACTION_ERROR = "extraction_error"


@dataclass
class ExtractionDecision:
    products: list[Product]
    outcome: ExtractionOutcomeType
    strategy_name: str = "none"
    method: str = "none"
    metadata: dict[str, Any] | None = None
    retry_strategy: CrawlPolicy | None = None


class ExtractionEngine:
    def __init__(
        self,
        strategies: dict[str, Any],
        policy_engine: ExtractionPolicyEngine,
    ):
        self.strategies = strategies
        self.policy_engine = policy_engine
        self.analyzer = PageAnalyzer()

    def extract(
        self,
        task: CrawlTask,
        page: Any,
        html: str,
    ) -> ExtractionDecision:
        site = task.site
        page_type = getattr(task.page_pattern, 'value', 'unknown')

        log.info("extraction_start", site=site, page_type=page_type,
                 available_strategies=list(self.strategies.keys()))

        from ai_crawler.extraction.templates.template_based import get_template
        template = get_template(site, page_type)
        if template and template.is_valid:
            result = template.extract(page, html, task.url)
            if result.products:
                log.info("extraction_template_success", site=site, products_count=len(result.products))
                self.policy_engine.record(site, page_type, "template", len(result.products), True)
                return self._to_decision(result, "template")

        features = self.analyzer.analyze(html, page)
        order = self.policy_engine.get_order(site, page_type, features)
        log.info("extraction_strategy_order", site=site, page_type=page_type, order=order, features=features)

        for strategy_name in order:
            if strategy_name not in self.strategies:
                log.warning("extraction_strategy_missing", site=site, strategy=strategy_name)
                continue
            extractor = self.strategies[strategy_name]
            try:
                if hasattr(extractor, 'extract'):
                    result = extractor.extract(page, html, task.url)
                    if isinstance(result, ExtractionResult):
                        products = result.products
                    else:
                        products = result
                else:
                    continue
                log.info("extraction_strategy_tried", site=site, strategy=strategy_name, products_count=len(products),
                         products_type=type(products).__name__, page_type=page_type)
                success = len(products) >= 2
                self.policy_engine.record(site, page_type, strategy_name, len(products), success)
                if products:
                    outcome = ExtractionOutcomeType.SUCCESS if len(products) >= 3 else ExtractionOutcomeType.PARTIAL_CONTENT
                    log.info("extraction_strategy_success", site=site, strategy=strategy_name, products_count=len(products))
                    return ExtractionDecision(
                        products=products,
                        outcome=outcome,
                        strategy_name=strategy_name,
                        method=getattr(extractor, 'method', strategy_name),
                    )
            except Exception as e:
                log.debug("extraction_failed", strategy=strategy_name, error=str(e))
                continue

        log.warning("extraction_all_failed", site=site, page_type=page_type)
        return ExtractionDecision(
            products=[],
            outcome=ExtractionOutcomeType.EMPTY_CONTENT,
        )

    def _to_decision(self, result: ExtractionResult, strategy_name: str) -> ExtractionDecision:
        outcome = ExtractionOutcomeType.SUCCESS if len(result.products) >= 3 else ExtractionOutcomeType.PARTIAL_CONTENT
        return ExtractionDecision(
            products=result.products,
            outcome=outcome,
            strategy_name=strategy_name,
            method=result.method,
        )
