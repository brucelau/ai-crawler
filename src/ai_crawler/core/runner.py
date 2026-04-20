from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import structlog
from collections import deque

from ai_crawler.browser.fetching import Fetcher

from ai_crawler.core.engine.captcha import CaptchaService
from ai_crawler.core.engine.execution import TaskExecutionEngine
from ai_crawler.core.engine.extraction_runtime import ExtractionRuntimeService
from ai_crawler.core.engine.handler import AntiBotHandler, BlockType
from ai_crawler.core.engine.outcomes import FailureOutcomeHandler, TraceRecorder
from ai_crawler.core.engine.planner import TaskStrategyPlanner
from ai_crawler.core.engine.processing import TaskProcessor
from ai_crawler.core.engine.proxying import ProxyProvider
from ai_crawler.core.engine.queue import CrawlQueue, SiteCircuitBreaker, SiteMemoryStore
from ai_crawler.core.engine.recommendation import DSPyStrategyRecommender
from ai_crawler.core.engine.results import CrawlResult
from ai_crawler.core.strategy import CrawlTask
from ai_crawler.core.engine.trace_store import TraceStore


log = structlog.get_logger()


class ConcurrencyController:
    def __init__(self, initial: int = 3, min_limit: int = 1, max_limit: int = 10):
        self._current = initial
        self._min = min_limit
        self._max = max_limit
        self._recent_outcomes: deque = deque(maxlen=50)
        self._lock = Lock()
        self._failure_threshold = 0.5

    def record_outcome(self, success: bool) -> None:
        with self._lock:
            self._recent_outcomes.append("success" if success else "failure")
            self._adjust()

    def _adjust(self) -> None:
        if len(self._recent_outcomes) < 10:
            return
        failures = sum(1 for o in self._recent_outcomes if o == "failure")
        failure_rate = failures / len(self._recent_outcomes)
        if failure_rate > self._failure_threshold:
            self._current = max(self._min, self._current - 1)
        elif failure_rate < 0.2 and self._current < self._max:
            self._current = min(self._max, self._current + 1)

    def get_limit(self) -> int:
        with self._lock:
            return self._current

    @property
    def max_workers(self) -> int:
        return self.get_limit()


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
        strategy_mode: str = "optimal",
        memory_store: SiteMemoryStore | None = None,
    ):
        self.queue = CrawlQueue(memory_store=memory_store)
        self.memory_store = memory_store
        self._circuit_breaker = SiteCircuitBreaker()
        self._concurrency = ConcurrencyController(initial=concurrency)
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
        self.strategy_mode = strategy_mode
        self._planner = TaskStrategyPlanner(trace_store=self.trace_store, strategy_mode=strategy_mode)
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

        if self.memory_store:
            sites = set()
            for task in list(self.queue.pending):
                sites.add(task.site)
            for site in sites:
                self.queue.load_site_memory(site)

        try:
            while self._running:
                pending, running, failed = self.queue.size()
                if pending == 0 and running == 0:
                    break

                if running >= self._concurrency.get_limit():
                    time.sleep(0.2)
                    continue

                task = self.queue.dequeue()
                if not task:
                    time.sleep(0.5)
                    continue

                if not self._circuit_breaker.is_available(task.site):
                    self.queue.pending.appendleft(task)
                    time.sleep(1)
                    continue

                if len(results) >= max_items:
                    self._running = False
                    break

                future = self.executor.submit(self._process_one, task)
                try:
                    result = future.result()
                    if result is None or not hasattr(result, "success"):
                        continue

                    results.append(result)

                    with self._results_lock:
                        self._results.append(result)

                    self._concurrency.record_outcome(result.success)
                    if result.success:
                        self._circuit_breaker.record_success(task.site)
                    else:
                        self._circuit_breaker.record_failure(task.site)

                except Exception as e:
                    log.error("task_error", task_id=task.task_id, error=str(e))
        finally:
            if self.memory_store:
                self.queue.save_site_memory()

        return results

    def run_async(self, max_items: int = 100) -> list[CrawlResult]:
        return self.run(max_items)

    def stop(self):
        self._running = False
        log.info("fetcher_stats", **self.fetcher.stats_snapshot())
        self.fetcher.close()
        self.executor.shutdown(wait=False)
