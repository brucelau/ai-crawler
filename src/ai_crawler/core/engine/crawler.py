from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from ai_crawler.core.task_context import TaskContext, Event
from ai_crawler.core.types import CrawlTask, CrawlStrategy
from ai_crawler.core.engine.results import CrawlResult

if TYPE_CHECKING:
    from ai_crawler.core.engine.policy_engine import PolicyEngine
    from ai_crawler.core.extraction.engine import ExtractionEngine
    from ai_crawler.core.engine.fetch_engineer import FetchEngineer

log = structlog.get_logger()


class Crawler:
    def __init__(
        self,
        id: int,
        policy_engine: PolicyEngine,
        extraction_engine: ExtractionEngine,
        execution: FetchEngineer,
        memory_store,
    ):
        self.id = id
        self.policy_engine = policy_engine
        self.extraction_engine = extraction_engine
        self.execution = execution
        self.memory_store = memory_store

    def execute(self, task: CrawlTask) -> CrawlResult:
        log.info("crawler_start", site=task.site, url=task.url, goal=getattr(task, 'goal', 'unknown'))

        ctx = TaskContext(task)
        strategy = self.policy_engine.ask(ctx)
        max_attempts = 5

        log.info("crawler_strategy_selected", site=task.site, tier=getattr(strategy, 'tier', '?'),
                 render=strategy.render.value if hasattr(strategy, 'render') else '?')

        while ctx.attempt_count < max_attempts:
            log.info("crawler_attempt", site=task.site, attempt=ctx.attempt_count + 1, max=max_attempts)

            attempt = self.execution.execute(task, strategy)

            event = Event(
                type="fetch",
                success=attempt is not None and not attempt.blocked,
                strategy=strategy,
                block_type=attempt.block_type if attempt else "",
                latency_ms=attempt.latency_ms if attempt else 0,
                html_size=len(attempt.html) if attempt and attempt.html else 0,
            )
            ctx.add_event(event)

            if attempt is None or attempt.blocked:
                log.warning("crawler_blocked", site=task.site, block_type=attempt.block_type if attempt else "None",
                           attempt=ctx.attempt_count + 1)
                ctx.add_tried_strategy(strategy)
                strategy = self.policy_engine.get_next(ctx)
                ctx.increment_attempt()
                continue

            log.info("crawler_extracting", site=task.site, html_size=len(attempt.html),
                     attempt=ctx.attempt_count + 1)

            extraction_result = self.extraction_engine.extract(
                task=task,
                page=attempt.page,
                html=attempt.html,
            )

            log.info("crawler_extracted", site=task.site, products_count=len(extraction_result.products),
                     strategy=extraction_result.strategy_name, method=extraction_result.method,
                     attempt=ctx.attempt_count + 1)

            if len(extraction_result.products) > 0:
                ctx.set_result(CrawlResult(
                    task=task,
                    strategy=strategy,
                    success=True,
                    html=attempt.html,
                    products=extraction_result.products,
                    extraction_strategy=extraction_result.strategy_name,
                    extraction_method=extraction_result.method,
                ))
                break

            ctx.add_tried_strategy(strategy)
            strategy = self.policy_engine.get_next(ctx)
            if strategy is None:
                ctx.set_result(CrawlResult(
                    task=task,
                    strategy=strategy,
                    success=False,
                    html=attempt.html,
                    products=[],
                    extraction_strategy=extraction_result.strategy_name,
                    extraction_method=extraction_result.method,
                    error="all strategies exhausted",
                ))
                break

            ctx.increment_attempt()
            continue

        if ctx.result is None:
            log.error("crawler_max_attempts", site=task.site, attempts=max_attempts)
            ctx.set_result(CrawlResult(
                task=task,
                strategy=strategy,
                success=False,
                error="Max attempts reached",
            ))

        log.info("crawler_done", site=task.site, success=ctx.result.success,
                 products_count=len(ctx.result.products) if ctx.result else 0)
        self.policy_engine.record(ctx)
        return ctx.result