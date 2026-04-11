from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from threading import Lock

from ai_crawler.core.strategy import CrawlTask, CrawlStrategy


@dataclass
class StrategyAttempt:
    task_id: str
    url: str
    site: str
    strategy: CrawlStrategy
    block_type: str
    response_snippet: str
    success: bool


@dataclass
class SiteMemory:
    site: str
    successful_strategies: list[CrawlStrategy] = field(default_factory=list)
    attempt_log: list[StrategyAttempt] = field(default_factory=list)
    llm_tier_cache: dict[str, int] = field(default_factory=dict)

    def record_success(self, strategy: CrawlStrategy):
        if strategy not in self.successful_strategies:
            self.successful_strategies.insert(0, strategy)

    def record_llm_tier(self, page_pattern: str, tier: int) -> None:
        self.llm_tier_cache[page_pattern] = tier

    def get_llm_tier(self, page_pattern: str) -> int | None:
        return self.llm_tier_cache.get(page_pattern)

    def recent_attempts(self, n: int = 5) -> list[StrategyAttempt]:
        return self.attempt_log[-n:]

    def get_failure_history_for_llm(self, page_pattern: str, n: int = 10) -> str:
        relevant_attempts = [
            a
            for a in self.attempt_log[-n:]
            if hasattr(a, "page_pattern") and a.page_pattern == page_pattern
        ]
        if not relevant_attempts:
            return ""
        history_parts = []
        for a in relevant_attempts[-5:]:
            history_parts.append(
                f"- Tier {getattr(a, 'strategy_tier', 1)}/{a.strategy_render}: "
                f"{a.block_type} (HTTP {getattr(a, 'status_code', 0)}, "
                f"WAF: {getattr(a, 'waf_detected', 'none')})"
            )
        return "\n".join(history_parts)


class CrawlQueue:
    def __init__(self):
        self.pending: deque[CrawlTask] = deque()
        self.running: dict[str, CrawlTask] = {}
        self.failed: list[CrawlTask] = []
        self.site_memory: dict[str, SiteMemory] = {}
        self._lock = Lock()

    def enqueue(self, tasks: list[CrawlTask]) -> None:
        with self._lock:
            for task in tasks:
                memory = self.site_memory.get(task.site)
                if memory and memory.successful_strategies:
                    best_strategy = memory.successful_strategies[0]
                    if not task.strategies or task.strategies[0] != best_strategy:
                        task.add_strategy_front(best_strategy)
                self.pending.append(task)

    def dequeue(self) -> CrawlTask | None:
        with self._lock:
            if not self.pending:
                return None
            task = self.pending.popleft()
            self.running[task.task_id] = task
            return task

    def on_success(self, task: CrawlTask, strategy_used: CrawlStrategy) -> None:
        with self._lock:
            self.running.pop(task.task_id, None)
            memory = self.site_memory.setdefault(task.site, SiteMemory(site=task.site))
            memory.record_success(strategy_used)

    def on_failure(
        self,
        task: CrawlTask,
        block_type: str,
        response_snippet: str,
    ) -> tuple[bool, CrawlStrategy | None]:
        with self._lock:
            self.running.pop(task.task_id, None)
            task.fail_count += 1

            if not task.exhausted():
                task.advance()
                self.pending.appendleft(task)
                return False, task.current_strategy()

            strategy_used = (
                task.strategies[task.current_index - 1]
                if task.current_index > 0
                else task.strategies[0]
            )
            attempt = StrategyAttempt(
                task_id=task.task_id,
                url=task.url,
                site=task.site,
                strategy=strategy_used,
                block_type=block_type,
                response_snippet=response_snippet[:1000],
                success=False,
            )
            memory = self.site_memory.setdefault(task.site, SiteMemory(site=task.site))
            memory.attempt_log.append(attempt)

            self.failed.append(task)
            return True, None

    def retry_failed(self) -> list[CrawlTask]:
        with self._lock:
            retried = []
            for task in self.failed:
                if task.fail_count < 3:
                    task.current_index = 0
                    self.pending.appendleft(task)
                    retried.append(task)
            self.failed = [t for t in self.failed if t not in retried]
            return retried

    def get_failed_tasks(self) -> list[CrawlTask]:
        return list(self.failed)

    def size(self) -> tuple[int, int, int]:
        with self._lock:
            return len(self.pending), len(self.running), len(self.failed)
