from __future__ import annotations

from dataclasses import dataclass
from typing import Any # 导入 Any

from ai_crawler.core.config import config, setup_logging
from ai_crawler.core.sites import SUPPORTED_SITES
from ai_crawler.crawl.runner import CrawlRunner
from ai_crawler.crawl.introspection import get_system_facts
from ai_crawler.storage.trace_store import TraceStore
from ai_crawler.core.types import CrawlTask, PagePattern, RuntimeBatchResult, RuntimeTask, RuntimeTaskResult
from ai_crawler.storage.backend import ProductOutputWriter
from ai_crawler.crawl.queue import MemoryStore


@dataclass(slots=True)
class RuntimeOptions:
    proxy_username: str = ""
    proxy_password: str = ""
    llm_api_key: str | None = None
    captcha_api_key: str | None = None
    output_dir: str = "output"
    traces_dir: str = "traces"
    max_ip_retries: int = 3
    proxy_disabled: bool = False
    concurrency: int = 1
    strategy_mode: str = "optimal"
    save_html: bool = False


class SmartCrawlerRuntime:
    def __init__(self, options: RuntimeOptions):
        self.options = options

    def build_search_tasks(self, sites: list[str], query: str, pages: int) -> list[RuntimeTask]:
        tasks: list[RuntimeTask] = []
        for site in sites:
            for page in range(1, pages + 1):
                url = self.build_search_url(site, query, page)
                if not url:
                    continue
                tasks.append(
                    RuntimeTask(
                        id=f"{site}-search-{page}",
                        site=site,
                        url=url,
                        goal="search",
                        metadata={"page": page, "query": query},
                    )
                )
        return tasks

    def build_detail_task(self, site: str, url: str) -> RuntimeTask:
        return RuntimeTask(id=f"{site}-detail", site=site, url=url, goal="detail")

    def crawl(self, sites: list[str], query: str, pages: int, storage_backend=None) -> RuntimeBatchResult:
        return self.crawl_tasks(self.build_search_tasks(sites, query, pages), storage_backend)

    def crawl_tasks(self, tasks: list[RuntimeTask], storage_backend=None) -> RuntimeBatchResult:

        setup_logging(log_level=config.LOG_LEVEL, log_dir=config.LOG_DIR, log_file=config.LOG_FILE)
        trace_store = TraceStore(storage_dir=self.options.traces_dir, backend=storage_backend)
        runner = self._build_runner(trace_store, storage_backend)

        # 从 runner 获取 memory_store
        memory_store = runner.memory_store
        # 确保 memory_store 不为 None
        if memory_store is None:
            memory_store = MemoryStore(storage_dir="site_memory", backend=storage_backend)

        crawl_tasks = [self._to_crawl_task(task, memory_store) for task in tasks]
        task_by_id = {task.id: task for task in tasks}
        runner.add_tasks(crawl_tasks)
        core_results = runner.run()

        # Save HTML if requested
        if self.options.save_html:
            import os
            html_dir = os.path.join(self.options.output_dir, "html")
            os.makedirs(html_dir, exist_ok=True)
            for result in (core_results or []):
                if result and result.html:
                    site = getattr(result.task, 'site', 'unknown')
                    import time
                    ts = time.strftime("%Y%m%d_%H%M%S")
                    html_path = os.path.join(html_dir, f"{site}_{ts}.html")
                    with open(html_path, "w") as f:
                        f.write(result.html)

        task_results: list[RuntimeTaskResult] = []
        for result in core_results or []:
            if result is None:
                continue
            task = getattr(result, "task", None)
            if task is None:
                continue
            tid = getattr(task, "task_id", None)
            if tid is None:
                continue
            if tid in task_by_id:
                task_results.append(RuntimeTaskResult.from_core_result(task_by_id[tid], result))

        output_files = ProductOutputWriter(self.options.output_dir, backend=storage_backend).write(task_results)
        products = [product for result in task_results for product in result.products]
        stats = trace_store.stats()
        stats["products_crawled"] = len(products)
        stats["tasks_total"] = len(task_results)
        stats["tasks_success"] = sum(1 for result in task_results if result.success)
        stats["task_extraction_strategies"] = {}
        stats["task_axtree_hits"] = 0
        for result in task_results:
            strategy_name = (result.artifacts or {}).get("extraction_strategy", "none")
            stats["task_extraction_strategies"][strategy_name] = (
                stats["task_extraction_strategies"].get(strategy_name, 0) + 1
            )
            if (result.artifacts or {}).get("axtree_hit"):
                stats["task_axtree_hits"] += 1

        return RuntimeBatchResult(
            products=products,
            task_results=task_results,
            stats=stats,
            output_files=output_files,
            traces_file=str(trace_store._session_file),
        )

    def _build_runner(self, trace_store: TraceStore, storage_backend=None) -> CrawlRunner:
        dynamic_profile = self._build_dynamic_profile(self.options.llm_api_key)
        captcha_solver = self._build_captcha_solver(self.options.captcha_api_key)
        memory_store = MemoryStore(storage_dir="site_memory", backend=storage_backend)
        runner = CrawlRunner(
            proxy_username=self.options.proxy_username,
            proxy_password=self.options.proxy_password,
            llm_api_key=self.options.llm_api_key,
            concurrency=self.options.concurrency,
            trace_store=trace_store,
            dynamic_profile=dynamic_profile,
            captcha_solver=captcha_solver,
            max_ip_retries=self.options.max_ip_retries,
            proxy_disabled=self.options.proxy_disabled,
            strategy_mode=self.options.strategy_mode,
            memory_store=memory_store,
        )

        if self.options.llm_api_key:
            from ai_crawler.llm.dspy_model import InitialTierSelector

            try:
                runner.set_initial_tier_selector(InitialTierSelector())
            except Exception:
                pass

        return runner

    def _to_crawl_task(self, task: RuntimeTask, memory_store: MemoryStore) -> CrawlTask:
        query = task.metadata.get("query")
        from ai_crawler.core.types import PagePattern
        goal_to_pattern = {
            "search": PagePattern.SEARCH,
            "detail": PagePattern.DETAIL,
            "category": PagePattern.SEARCH,
            "reviews": PagePattern.REVIEW,
        }
        page_pattern = goal_to_pattern.get(task.goal, PagePattern.UNKNOWN)
        loaded = memory_store.load(task.site)
        memory_key = (task.site, page_pattern.value)
        site_memory = loaded.get(memory_key)

        crawl_task = CrawlTask(
            url=task.url,
            site=task.site,
            page_pattern=page_pattern,
            query=query,
            site_memory=site_memory,
        )
        crawl_task.task_id = task.id
        crawl_task.metadata.update(task.metadata)
        crawl_task.metadata["goal"] = task.goal
        crawl_task.metadata["session_policy"] = task.session_policy
        crawl_task.metadata["extraction_mode"] = task.extraction_mode
        return crawl_task

    def _build_dynamic_profile(self, llm_api_key: str | None) -> dict[str, Any]:
        if not llm_api_key:
            return {}

        from ai_crawler.llm.dspy_model import ProfileGenerator
        from typing import Any # 导入 Any

        try:
            profile_gen = ProfileGenerator()
            res = profile_gen(system_facts=get_system_facts())
            return {
                "user_agent": res.user_agent,
                "sec_ch_ua_platform": res.sec_ch_ua_platform,
                "sec_ch_ua": res.sec_ch_ua,
                "stealth_args": res.stealth_args,
                "curl_impersonate_target": res.curl_impersonate_target,
                "timezone_id": res.timezone_id,
                "locale": res.locale,
                "viewport": res.viewport,
                "mouse_behavior": res.mouse_behavior,
            }
        except Exception:
            return {}

    def _build_captcha_solver(self, captcha_api_key: str | None):
        if not captcha_api_key:
            return None
        from ai_crawler.antidetect.captcha.solver import CaptchaSolver

        return CaptchaSolver(captcha_api_key)

    @staticmethod
    def build_search_url(site: str, query: str, page: int) -> str:
        template = SUPPORTED_SITES.get(site)
        if not template:
            return ""
        q = query.replace(" ", "+")
        url = template.format(query=q)
        if page > 1:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}page={page}"
        return url
