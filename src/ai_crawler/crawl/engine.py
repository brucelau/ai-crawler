from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from ai_crawler.crawl.planner import Planner
from ai_crawler.crawl.task_context import TaskContext, Event
from ai_crawler.crawl.strategy import build_policy
from ai_crawler.core.types import CrawlTask, CrawlPolicy, SiteMemory
from ai_crawler.crawl.results import CrawlResult
from ai_crawler.sites.registry import get_command

if TYPE_CHECKING:
    from ai_crawler.extraction import ExtractionEngine
    from ai_crawler.fetch.engineer import FetchEngineer

log = structlog.get_logger()


class Crawler:
    def __init__(
        self,
        id: int,
        policy_engine: Planner,
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

        # WAF probe: one-shot detection for first-time crawls.
        # If the probe succeeds (not blocked), try extracting directly to avoid
        # unnecessary escalation to heavier renderers.
        probe = _probe_waf(task, self.execution)
        if probe is not None and not probe.blocked and probe.html:
            log.info("crawler_probe_success", site=task.site, html_size=len(probe.html))
            adapter = _get_adapter(task)
            if adapter is not None:
                # Try API extraction first (goes through proxy)
                products = _try_api_extraction(adapter, task, self.execution)
                if products:
                    extraction_method = "adapter_api"
                    extraction_strategy = f"{adapter.site}.{adapter.command}.api"
                else:
                    products = adapter.extract(probe.html, task.url)
                    extraction_method = "adapter"
                    extraction_strategy = f"{adapter.site}.{adapter.command}"
            else:
                extraction_result = self.extraction_engine.extract(
                    task=task, page=probe.page, html=probe.html,
                )
                products = extraction_result.products
                extraction_method = extraction_result.method
                extraction_strategy = extraction_result.strategy_name
            if len(products) > 0:
                log.info("crawler_probe_extracted", site=task.site, products_count=len(products))
                result = CrawlResult(
                    task=task, strategy=build_policy(0), success=True,
                    html=probe.html, products=products,
                    extraction_strategy=extraction_strategy, extraction_method=extraction_method,
                )
                ctx.set_result(result)
                self.policy_engine.record(ctx)
                return result
            log.info("crawler_probe_no_products", site=task.site,
                     extraction_strategy=extraction_strategy)

        strategy = self.policy_engine.ask(ctx)
        max_attempts = 7

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
                waf_type=attempt.waf_detected if attempt else "",
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

            # Try site adapter first, fall back to generic extraction engine
            adapter = _get_adapter(task)
            if adapter is not None:
                # Try API extraction first (goes through proxy)
                products = _try_api_extraction(adapter, task, self.execution)
                if products:
                    extraction_method = "adapter_api"
                    extraction_strategy = f"{adapter.site}.{adapter.command}.api"
                else:
                    products = adapter.extract(attempt.html, task.url)
                    extraction_method = "adapter"
                    extraction_strategy = f"{adapter.site}.{adapter.command}"
            else:
                extraction_result = self.extraction_engine.extract(
                    task=task,
                    page=attempt.page,
                    html=attempt.html,
                )
                products = extraction_result.products
                extraction_method = extraction_result.method
                extraction_strategy = extraction_result.strategy_name

            log.info("crawler_extracted", site=task.site, products_count=len(products),
                     strategy=extraction_strategy, method=extraction_method,
                     attempt=ctx.attempt_count + 1)

            if len(products) > 0:
                ctx.set_result(CrawlResult(
                    task=task,
                    strategy=strategy,
                    success=True,
                    html=attempt.html,
                    products=products,
                    extraction_strategy=extraction_strategy,
                    extraction_method=extraction_method,
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
                    extraction_strategy=extraction_strategy,
                    extraction_method=extraction_method,
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


def _try_api_extraction(adapter, task, execution) -> list[Product] | None:
    """If adapter has api_url_template, fetch via proxy and call extract_api."""
    if not adapter.api_url_template:
        return None
    query = getattr(task, 'query', None)
    if not query:
        log.debug("api_extraction_skip_no_query", site=adapter.site)
        return None
    try:
        api_url = adapter.build_api_url(query=query)
        api_params = adapter.build_api_params(query)
        data = execution.fetch_api(api_url, api_params)
        if data is not None:
            products = adapter.extract_api(data)
            log.info("api_extraction_ok", site=adapter.site, products_count=len(products))
            return products
        else:
            log.info("api_extraction_fetch_failed", site=adapter.site, api_url=api_url[:80])
    except Exception as exc:
        log.warning("api_extraction_error", site=adapter.site, error=str(exc))
    return None


def _get_adapter(task: CrawlTask):
    """Return a Command instance for the task's site + page_pattern, or None."""
    pattern = getattr(task.page_pattern, 'value', 'unknown')
    cls = get_command(task.site, pattern)
    if cls is not None:
        return cls()
    # Fallback: try to find any command for this site
    from ai_crawler.sites.registry import list_commands
    cmds = list_commands(task.site)
    if cmds:
        cls = get_command(task.site, cmds[0])
        if cls is not None:
            return cls()
    return None


def _probe_waf(task: CrawlTask, execution):
    """One-shot WAF detection for first-time crawls.

    Does a single lightweight fetch at level 0 and records the WAF type
    in site memory. Returns the Attempt if it succeeded (caller can try
    extracting from it), or None if WAF is already known or probe failed.
    """
    if task.site_memory and task.site_memory.waf_type:
        return None

    try:
        probe = execution.execute(task, build_policy(0))
        if probe is None:
            return None
        if probe.waf_detected:
            if not task.site_memory:
                task.site_memory = SiteMemory(site=task.site, page_pattern=task.page_pattern.value)
            task.site_memory.waf_type = probe.waf_detected
            log.info("crawler_waf_probe", site=task.site, waf_type=probe.waf_detected)
        if not probe.blocked and probe.html:
            return probe
    except Exception:
        pass
    return None