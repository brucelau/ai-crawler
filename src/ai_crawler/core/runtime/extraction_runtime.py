from __future__ import annotations

from dataclasses import dataclass

from ai_crawler.core.extraction import ExtractionResult
from ai_crawler.core.strategy import CrawlStrategy, CrawlTask, RenderType


@dataclass(slots=True)
class ExtractionDecision:
    products: list
    should_retry: bool
    retry_reason: str | None = None
    strategy_name: str = "none"
    method: str = "none"
    metadata: dict | None = None


class ExtractionRuntimeService:
    def __init__(self, extraction_chains: dict[str, any]):
        self.extraction_chains = extraction_chains

    @staticmethod
    def _resolve_page_type(task: CrawlTask) -> str:
        page_type = getattr(task.page_pattern, "value", "unknown")
        if page_type and page_type != "unknown":
            return page_type
        goal = str(task.metadata.get("goal", "") or "")
        if goal == "reviews":
            return "review"
        return goal or "unknown"

    def extract(
        self, task: CrawlTask, strategy: CrawlStrategy, page, html: str
    ) -> ExtractionDecision:
        chain = self.extraction_chains.get(task.site)
        page_type = self._resolve_page_type(task)
        if chain:
            extraction_result = chain.extract(page, html, task.url, page_type=page_type)
        else:
            extraction_result = ExtractionResult(products=[], strategy="none", method="none")

        products = extraction_result.products
        if products:
            return ExtractionDecision(
                products=products,
                should_retry=False,
                strategy_name=extraction_result.strategy,
                method=extraction_result.method,
                metadata={"axtree_hit": extraction_result.strategy == "axtree"},
            )

        if html:
            from ai_crawler.core.llm.llm_extractor import extract_with_llm_page

            llm_products = extract_with_llm_page(
                html,
                page,
                task.site,
                self._resolve_page_type(task),
                task.url,
            )
            if not llm_products:
                llm_products = extract_with_llm_page(
                    html,
                    page,
                    task.site,
                    self._resolve_page_type(task),
                    task.url,
                    force_regenerate=True,
                )
            if llm_products:
                return ExtractionDecision(
                    products=llm_products,
                    should_retry=False,
                    strategy_name="llm_selector_fallback",
                    method="llm_selector",
                    metadata={"axtree_hit": page is not None},
                )

        if strategy.render in (
            RenderType.NONE,
            RenderType.PLAYWRIGHT,
            RenderType.CLOUDSCRAPER,
            RenderType.CLOUDERA,
            RenderType.SELENIUMBASE,
            RenderType.CAMOUFOX,
            RenderType.CLOAKBROWSER,
        ):
            if strategy.render in (RenderType.NONE, RenderType.PLAYWRIGHT, RenderType.CLOUDSCRAPER):
                upgrade_render = RenderType.CAMOUFOX
                if strategy.render == RenderType.NONE and "costway.com" in task.url:
                    upgrade_render = RenderType.CLOUDSCRAPER
            elif strategy.render == RenderType.CAMOUFOX:
                upgrade_render = RenderType.CLOAKBROWSER
            else:
                upgrade_render = None

            if upgrade_render:
                upgrade = CrawlStrategy(
                    proxy=strategy.proxy,
                    render=upgrade_render,
                    change_ua=True,
                    use_human_scroll=True,
                )
                task.add_strategy_next(upgrade)
            return ExtractionDecision(
                products=[],
                should_retry=True,
                retry_reason="empty_content",
                strategy_name=extraction_result.strategy,
                method=extraction_result.method,
                metadata={"axtree_hit": extraction_result.strategy == "axtree"},
            )

        return ExtractionDecision(
            products=[],
            should_retry=False,
            strategy_name=extraction_result.strategy,
            method=extraction_result.method,
            metadata={"axtree_hit": extraction_result.strategy == "axtree"},
        )
