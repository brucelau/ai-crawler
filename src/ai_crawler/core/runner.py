from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import structlog

from ai_crawler.browser.fetching import Fetcher

from ai_crawler.core.runtime.captcha import CaptchaService
from ai_crawler.core.runtime.execution import TaskExecutionEngine
from ai_crawler.core.runtime.extraction_runtime import ExtractionRuntimeService
from ai_crawler.core.runtime.handler import AntiBotHandler, BlockType
from ai_crawler.core.runtime.outcomes import FailureOutcomeHandler, TraceRecorder
from ai_crawler.core.runtime.planner import TaskStrategyPlanner
from ai_crawler.core.runtime.processing import TaskProcessor
from ai_crawler.core.runtime.proxying import ProxyProvider
from ai_crawler.core.runtime.queue import CrawlQueue
from ai_crawler.core.runtime.recommendation import DSPyStrategyRecommender
from ai_crawler.core.runtime.results import CrawlResult
from ai_crawler.core.strategy import CrawlTask
from ai_crawler.core.runtime.trace_store import TraceStore


log = structlog.get_logger()


class CrawlRunner:
    IP_ROTATION_BLOCK_TYPES = {
        BlockType.HTTP_403,
        BlockType.HTTP_429,
        BlockType.HTTP_451,
        BlockType.HTTP_TIMEOUT,
        BlockType.BOT_DETECTED,
        BlockType.CLOUDFLARE,
        BlockType.EMPTY_RESPONSE,
    }

    def __init__(
        self,
        proxy_username: str,
        proxy_password: str,
        llm_api_key: str | None = None,
        concurrency: int = 3,
        trace_store: TraceStore | None = None,
        dspy_model=None,
        dynamic_profile: dict | None = None,
        captcha_solver=None,
        max_ip_retries: int = 3,
        proxy_disabled: bool = False,
    ):
        self.queue = CrawlQueue()
        self.proxy_provider = ProxyProvider(proxy_username, proxy_password, disabled=proxy_disabled)
        self.fetcher = Fetcher(self.proxy_provider, dynamic_profile)
        self.anti_bot = AntiBotHandler()
        self._captcha = CaptchaService(captcha_solver)
        self.executor = ThreadPoolExecutor(max_workers=concurrency)
        self._running = False
        self._results: list[CrawlResult] = []
        self._results_lock = Lock()
        self.trace_store = trace_store or TraceStore()
        self.captcha_solver = captcha_solver
        self.max_ip_retries = max_ip_retries
        self._planner = TaskStrategyPlanner(trace_store=self.trace_store)
        self._execution = TaskExecutionEngine(
            self.fetcher,
            self.anti_bot,
            self.proxy_provider,
            max_ip_retries,
            self.IP_ROTATION_BLOCK_TYPES,
        )
        self._recommender = DSPyStrategyRecommender(dspy_model)
        self._trace_recorder = TraceRecorder(self.trace_store)
        self._failure_handler = FailureOutcomeHandler(
            self.queue,
            self._recommender if dspy_model else None,
            self._trace_recorder,
            planner=self._planner,
        )

        from ai_crawler.core.extraction import SITE_EXTRACTION_CHAINS

        self._extraction_chains = SITE_EXTRACTION_CHAINS
        self._extraction = ExtractionRuntimeService(self._extraction_chains)
        self._processor = TaskProcessor(
            queue=self.queue,
            planner=self._planner,
            execution=self._execution,
            captcha=self._captcha,
            fetcher=self.fetcher,
            anti_bot=self.anti_bot,
            trace_recorder=self._trace_recorder,
            failure_handler=self._failure_handler,
            extraction=self._extraction,
            captcha_solver=self.captcha_solver,
        )

    def add_tasks(self, tasks: list[CrawlTask]):
        self.queue.enqueue(tasks)

    def set_initial_tier_selector(self, selector):
        self._planner.set_initial_tier_selector(selector)

    def _process_one(self, task: CrawlTask) -> CrawlResult:
        return self._processor.process(task)

    def run(self, max_items: int = 100) -> list[CrawlResult]:
        self._running = True
        results = []

        while self._running:
            pending, running, failed = self.queue.size()
            if pending == 0 and running == 0:
                break

            task = self.queue.dequeue()
            if not task:
                time.sleep(0.5)
                continue

            if len(results) >= max_items:
                self._running = False
                break

            future = self.executor.submit(self._process_one, task)
            try:
                result = future.result()
                results.append(result)

                with self._results_lock:
                    self._results.append(result)

            except Exception as e:
                log.error("task_error", task_id=task.task_id, error=str(e))

        return results

    def run_async(self, max_items: int = 100) -> list[CrawlResult]:
        return self.run(max_items)

    def stop(self):
        self._running = False
        log.info("fetcher_stats", **self.fetcher.stats_snapshot())
        self.fetcher.close()
        self.executor.shutdown(wait=False)
