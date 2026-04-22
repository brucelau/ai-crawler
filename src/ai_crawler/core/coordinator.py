from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import TYPE_CHECKING

import structlog

from ai_crawler.core.types import CrawlTask

if TYPE_CHECKING:
    from ai_crawler.core.engine.crawler import Crawler
    from ai_crawler.core.engine.policy_engine import PolicyEngine
    from ai_crawler.core.extraction.engine import ExtractionEngine

log = structlog.get_logger()


class CrawlCoordinator:
    def __init__(
        self,
        policy_engine,
        extraction_engine,
        memory_store,
        num_crawlers: int = 3,
        executor: ThreadPoolExecutor | None = None,
    ):
        self.policy_engine = policy_engine
        self.extraction_engine = extraction_engine
        self.memory_store = memory_store
        self.num_crawlers = num_crawlers
        self.executor = executor
        self.crawlers: list[Crawler] = []

    def add_crawler(self, crawler: Crawler):
        self.crawlers.append(crawler)

    def run(self, tasks: list[CrawlTask]) -> list:
        if not self.crawlers:
            log.warning("no_crawlers_available")
            return []

        results = []
        exec = self.executor or ThreadPoolExecutor(max_workers=len(self.crawlers))
        own_executor = self.executor is None
        try:
            def execute_with_crawler(task, crawler_index):
                crawler = self.crawlers[crawler_index]
                return crawler.execute(task)

            futures = [
                exec.submit(partial(execute_with_crawler, crawler_index=i % len(self.crawlers)), task)
                for i, task in enumerate(tasks)
            ]
            for future in futures:
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    log.error("task_execution_error", error=str(e))
                    results.append(None)
        finally:
            if own_executor:
                exec.shutdown(wait=False)
        return results

    def _execute_one(self, task: CrawlTask, crawler_index: int):
        crawler = self.crawlers[crawler_index]
        return crawler.execute(task)
