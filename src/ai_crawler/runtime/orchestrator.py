from __future__ import annotations

from dataclasses import dataclass

from ai_crawler.config import setup_logging
from ai_crawler.core.runner import CrawlRunner
from ai_crawler.core.runtime.introspection import get_system_facts
from ai_crawler.core.runtime.trace_store import TraceStore
from ai_crawler.core.strategy import CrawlTask, PagePattern
from ai_crawler.runtime.models import RuntimeBatchResult, RuntimeTask, RuntimeTaskResult
from ai_crawler.runtime.storage import ProductOutputWriter


SUPPORTED_SITES = {
    "amazon": "https://www.amazon.com/s?k={query}",
    "walmart": "https://www.walmart.com/search?q={query}",
    "target": "https://www.target.com/s?searchTerm={query}",
    "ebay": "https://www.ebay.com/sch/i.html?_nkw={query}",
    "menards": "https://www.menards.com/main/search.html?query={query}",
    "lowes": "https://www.lowes.com/search?searchTerm={query}",
    "homedepot": "https://www.homedepot.com/search?text={query}",
    "acehardware": "https://www.acehardware.com/search?query={query}",
    "wayfair": "https://www.wayfair.com/keyword.php?keyword={query}",
    "michaels": "https://www.michaels.com/search?search={query}",
    "temu": "https://www.temu.com/search?search_key={query}",
    "etsy": "https://www.etsy.com/search?q={query}",
    "bestbuy": "https://www.bestbuy.com/site/search?search={query}",
    "costco": "https://www.costco.com/search?search={query}",
    "qvc": "https://www.qvc.com/forms/search/results?baseCountry=us&language=en-US&search={query}",
    "kohls": "https://www.kohls.com/search.jsp?search={query}",
    "mercadolibre": "https://listado.mercadolibre.com.mx/{query}",
    "walmartmexico": "https://www.walmartmexico.com.mx/search?term={query}",
    "intexcorp": "https://www.intexcorp.com/search?q={query}",
    "meijer": "https://www.meijer.com/shopping/search/{query}",
    "fivebelow": "https://www.fivebelow.com/search?q={query}",
    "samsclub": "https://www.samsclub.com/search?query={query}",
    "bunnings": "https://www.bunnings.com.au/search?query={query}",
    "dollargeneral": "https://www.dollargeneral.com/search?text={query}",
    "action": "https://www.action.com/search?q={query}",
    "academy": "https://www.academy.com/shop/search?q={query}",
    "wowsports": "https://wowsports.com/search?q={query}",
    "coppel": "https://www.coppel.com/search?term={query}",
    "aosom": "https://www.aosom.com/search?q={query}",
    "familydollar": "https://www.familydollar.com/search?q={query}",
    "costway": "https://www.costway.com/search?q={query}",
}


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

    def crawl(self, sites: list[str], query: str, pages: int) -> RuntimeBatchResult:
        return self.crawl_tasks(self.build_search_tasks(sites, query, pages))

    def crawl_tasks(self, tasks: list[RuntimeTask]) -> RuntimeBatchResult:
        from ai_crawler.config import config

        setup_logging(log_level=config.LOG_LEVEL, log_dir=config.LOG_DIR, log_file=config.LOG_FILE)
        trace_store = TraceStore(storage_dir=self.options.traces_dir)
        runner = self._build_runner(trace_store)

        crawl_tasks = [self._to_crawl_task(task) for task in tasks]
        task_by_id = {task.id: task for task in tasks}
        runner.add_tasks(crawl_tasks)
        core_results = runner.run()

        task_results = [
            RuntimeTaskResult.from_core_result(task_by_id[result.task.task_id], result)
            for result in core_results
            if result.task.task_id in task_by_id
        ]

        output_files = ProductOutputWriter(self.options.output_dir).write(task_results)
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

    def _build_runner(self, trace_store: TraceStore) -> CrawlRunner:
        dynamic_profile = self._build_dynamic_profile(self.options.llm_api_key)
        captcha_solver = self._build_captcha_solver(self.options.captcha_api_key)
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
        )

        if self.options.llm_api_key:
            from ai_crawler.core.llm.dspy_model import InitialTierSelector

            try:
                runner.set_initial_tier_selector(InitialTierSelector())
            except Exception:
                pass

        return runner

    def _to_crawl_task(self, task: RuntimeTask) -> CrawlTask:
        page_pattern = PagePattern.DETAIL if task.goal == "detail" else None
        crawl_task = CrawlTask.create_from_tier(
            url=task.url, site=task.site, page_pattern=page_pattern
        )
        crawl_task.task_id = task.id
        crawl_task.metadata.update(task.metadata)
        crawl_task.metadata["goal"] = task.goal
        crawl_task.metadata["session_policy"] = task.session_policy
        crawl_task.metadata["extraction_mode"] = task.extraction_mode
        return crawl_task

    def _build_dynamic_profile(self, llm_api_key: str | None) -> dict:
        if not llm_api_key:
            return {}

        from ai_crawler.core.llm.dspy_model import ProfileGenerator

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
        from ai_crawler.captcha import CaptchaSolver

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
