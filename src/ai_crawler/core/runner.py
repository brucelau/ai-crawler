from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from collections import deque
from typing import Any, Sequence # 导入 Any, Sequence

import structlog

from ai_crawler.browser.fetching import Fetcher

from ai_crawler.core.engine.captcha import CaptchaService
from ai_crawler.core.engine.fetch_engineer import FetchEngineer
from ai_crawler.core.engine.handler import AntiBotHandler, BlockType
from ai_crawler.core.engine.outcomes import FailureOutcomeHandler, TraceRecorder
from ai_crawler.core.engine.planner import Planner
from ai_crawler.core.engine.proxying import ProxyProvider
from ai_crawler.core.engine.queue import Queue, SiteCircuitBreaker, MemoryStore
from ai_crawler.core.engine.recommendation import DSPyStrategyRecommender
from ai_crawler.core.engine.results import CrawlResult
from ai_crawler.core.types import CrawlTask
from ai_crawler.core.engine.trace_store import TraceStore


log = structlog.get_logger()


class Concurrency:
    def __init__(self, initial: int = 3, min_limit: int = 1, max_limit: int = 10):
        self._current = initial
        self._min = min_limit
        self._max = max_limit
        self._recent_outcomes: deque[str] = deque(maxlen=50) # 指定类型参数
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
        dspy_model: Any = None,
        dynamic_profile: dict[str, Any] | None = None, # 指定类型参数
        captcha_solver: Any = None,
        max_ip_retries: int = 3,
        proxy_disabled: bool = False,
        strategy_mode: str = "optimal",
        memory_store: MemoryStore | None = None,
    ):
        self.queue = Queue(memory_store=memory_store)
        self.memory_store = memory_store
        self._circuit_breaker = SiteCircuitBreaker()
        self._concurrency = Concurrency(initial=concurrency)
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
        self._planner = Planner(trace_store=self.trace_store, strategy_mode=strategy_mode)
        self._execution = FetchEngineer(
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

        from ai_crawler.core.engine.crawler import Crawler
        from ai_crawler.core.coordinator import CrawlCoordinator
        from ai_crawler.core.extraction.engine import ExtractionEngine
        from ai_crawler.core.extraction.policy_engine import ExtractionPolicyEngine
        from ai_crawler.core.extraction.registry import create_strategy, list_strategies

        extraction_strategies = {name: create_strategy(name) for name in list_strategies()}
        self._extraction_policy_engine = ExtractionPolicyEngine(memory_store=memory_store)
        self._extraction = ExtractionEngine(
            strategies=extraction_strategies,
            policy_engine=self._extraction_policy_engine,
        )
        self._crawlers = [
            Crawler(
                id=i,
                policy_engine=self._planner,
                extraction_engine=self._extraction,
                execution=self._execution,
                memory_store=self.memory_store,
            )
            for i in range(concurrency)
        ]
        self._coordinator = CrawlCoordinator(
            policy_engine=self._planner,
            extraction_engine=self._extraction,
            memory_store=self.memory_store,
            num_crawlers=concurrency,
            executor=self.executor,
        )
        for crawler in self._crawlers:
            self._coordinator.add_crawler(crawler)

    def add_tasks(self, tasks: list[CrawlTask]):
        self.queue.enqueue(tasks)

    def set_initial_tier_selector(self, selector: Any):
        self._planner.set_initial_tier_selector(selector)

    def run(self, max_items: int = 100) -> list[CrawlResult]:
        self._running = True
        results: list[CrawlResult] = []

        if self.memory_store:
            sites = set()
            for task in list(self.queue.pending):
                sites.add(task.site)
            for site in sites:
                self.queue.load_site_memory(site)

        tasks_to_run = []
        for task in list(self.queue.pending)[:max_items]:
            if not self._circuit_breaker.is_available(task.site):
                continue
            tasks_to_run.append(task)
            self.queue.pending.remove(task)

        if tasks_to_run:
            new_results = self._coordinator.run(tasks_to_run)
            for result in new_results:
                if result is None or not hasattr(result, "success"):
                    continue
                results.append(result)
                with self._results_lock:
                    self._results.append(result)
                self._concurrency.record_outcome(result.success)
                task = result.task
                if result.success:
                    self._circuit_breaker.record_success(task.site)
                else:
                    self._circuit_breaker.record_failure(task.site)

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
