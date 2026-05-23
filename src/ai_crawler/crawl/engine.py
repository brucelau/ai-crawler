from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING

import structlog

from ai_crawler.crawl.planner import Planner
from ai_crawler.crawl.task_context import TaskContext, Event
from ai_crawler.crawl.strategy import build_policy
from ai_crawler.core.types import CrawlTask, CrawlPolicy, SiteMemory, Product
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
                if strategy is None:
                    ctx.set_result(CrawlResult(
                        task=task,
                        strategy=build_policy(6),
                        success=False,
                        html=attempt.html if attempt else "",
                        error="all strategies exhausted",
                    ))
                    break
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
                # Enrich products with detail page data using the same browser session.
                if attempt.page is not None and task.page_pattern and task.page_pattern.value == "search":
                    products = _crawl_details(
                        page=attempt.page, adapter=adapter,
                        products=products, search_url=task.url,
                        max_pages=5,
                    )

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
                    strategy=build_policy(6),
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
                strategy=strategy if strategy is not None else build_policy(6),
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


def _crawl_details(
    page, adapter, products: list[Product],
    search_url: str, max_pages: int = 5,
) -> list[Product]:
    """Visit product detail pages within the same browser session.

    Opens a fresh page from the same browser context (preserving cookies/session)
    so the search page stays intact. Visits the site homepage first to establish
    session cookies, then navigates to each detail page with human-like delays.
    """
    from urllib.parse import urlparse

    # Get the raw page (unwrap BrowserOperator if needed) and create a
    # fresh page from the same browser instance to preserve session cookies.
    raw_page = page._page if hasattr(page, '_page') else page
    try:
        detail_page = raw_page.context.new_page()
    except Exception:
        detail_page = raw_page.context.browser.new_page()

    try:
        # Warm up session by visiting the homepage first.
        parsed = urlparse(search_url)
        homepage = f"{parsed.scheme}://{parsed.netloc}"
        try:
            detail_page.goto(homepage, wait_until="commit", timeout=15000)
            detail_page.wait_for_selector("body", timeout=15000)
            time.sleep(random.uniform(2.0, 4.0))
        except Exception:
            pass

        enriched: list[Product] = []
        attempted = 0

        for product in products:
            url = getattr(product, 'url', '')
            if not url or not url.startswith('http'):
                enriched.append(product)
                continue
            if attempted >= max_pages:
                enriched.append(product)
                continue

            attempted += 1
            delay = random.uniform(5.0, 10.0)
            time.sleep(delay)

            try:
                resp = detail_page.goto(url, referer=search_url,
                                        wait_until="commit", timeout=15000)
                if resp and resp.status >= 400:
                    log.info("detail_crawl_http_error", url=url[:80], status=resp.status)
                    enriched.append(product)
                    continue
                # Wait for body to be present (domcontentloaded may never fire
                # on sites like eBay when ad/script blocking intercepts requests).
                detail_page.wait_for_selector("body", timeout=15000)
                time.sleep(random.uniform(2.0, 3.0))
            except Exception:
                log.info("detail_crawl_timeout", url=url[:80])
                enriched.append(product)
                continue

            # Wait for page to settle, scroll down to trigger lazy content
            time.sleep(random.uniform(1.0, 2.0))
            try:
                detail_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(random.uniform(1.0, 2.0))
                detail_page.evaluate("window.scrollTo(0, 0)")
            except Exception:
                pass

            html = detail_page.content()
            title = detail_page.title()

            if "Pardon Our Interruption" in title or "Access Denied" in title:
                log.info("detail_crawl_blocked", url=url[:80])
                enriched.append(product)
                continue

            log.info("detail_crawl_ok", url=url[:80],
                     title=title[:80], html_size=len(html))

            # Extract detail fields via adapter or generic fallback
            detail: dict = {}
            if adapter is not None and hasattr(adapter, 'extract_detail'):
                try:
                    detail = adapter.extract_detail(html, url)
                except Exception:
                    pass

            if detail:
                enriched.append(_merge_detail(product, detail))
                log.info("detail_crawl_enriched", url=url[:60],
                         fields=list(detail.keys()))
            else:
                enriched.append(product)

        return enriched
    finally:
        try:
            detail_page.close()
        except Exception:
            pass


def _merge_detail(product: Product, detail: dict) -> Product:
    """Merge extracted detail fields into a Product, never overwriting non-empty values."""
    for field in ('price', 'currency', 'rating', 'review_count', 'brand',
                  'description', 'availability', 'seller', 'shipping', 'category'):
        val = detail.get(field)
        if val is not None and val != "" and val != 0:
            existing = getattr(product, field, None)
            if existing is None or existing == "" or existing == 0:
                setattr(product, field, val)
    return product