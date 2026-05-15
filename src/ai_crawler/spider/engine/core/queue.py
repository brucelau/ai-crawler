from __future__ import annotations

import json
import os
import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

import structlog

log = structlog.get_logger()

from ai_crawler.spider.runtime.crawl import CrawlTask, CrawlPolicy, SiteMemory, MemoryStore, StrategyAttempt, PagePattern


class Queue:
    def __init__(self, memory_store: MemoryStore | None = None):
        self.pending: deque[CrawlTask] = deque()
        self.running: dict[str, CrawlTask] = {}
        self.failed: list[CrawlTask] = []
        self.site_memory: dict[tuple[str, str], SiteMemory] = {}
        self.memory_store = memory_store
        self._lock = Lock()

    def load_site_memory(self, site: str) -> None:
        if self.memory_store:
            loaded = self.memory_store.load(site)
            for key, memory in loaded.items():
                if key not in self.site_memory:
                    self.site_memory[key] = memory

    def save_site_memory(self) -> None:
        if self.memory_store:
            self.memory_store.save(self.site_memory)

    def _memory_key(self, site: str, page_pattern: str) -> tuple[str, str]:
        return (site, page_pattern)

    def enqueue(self, tasks: list[CrawlTask], group_by_site: bool = True) -> None:
        with self._lock:
            if group_by_site:
                tasks = sorted(tasks, key=lambda t: t.site)
            for task in tasks:
                key = self._memory_key(task.site, task.page_pattern.value)
                memory = self.site_memory.get(key)
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

    def on_success(self, task: CrawlTask, strategy_used: CrawlPolicy) -> None:
        with self._lock:
            self.running.pop(task.task_id, None)
            key = self._memory_key(task.site, task.page_pattern.value)
            memory = self.site_memory.setdefault(key, SiteMemory(site=task.site, page_pattern=task.page_pattern.value))
            memory.record_success(strategy_used)

    def record_extraction_quality(
        self, task: CrawlTask, method: str, outcome: str, product_count: int
    ) -> None:
        with self._lock:
            key = self._memory_key(task.site, task.page_pattern.value)
            memory = self.site_memory.setdefault(key, SiteMemory(site=task.site, page_pattern=task.page_pattern.value))
            memory.record_extraction_quality(method, outcome, product_count)

    def on_failure(
        self,
        task: CrawlTask,
        block_type: str,
        response_snippet: str,
    ) -> tuple[bool, CrawlPolicy | None]:
        with self._lock:
            self.running.pop(task.task_id, None)
            task.fail_count += 1

            if (task.current_index + 1) < len(task.strategies):
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
                page_pattern=task.page_pattern.value,
                strategy=strategy_used,
                block_type=block_type,
                response_snippet=response_snippet[:1000],
                success=False,
            )
            key = self._memory_key(task.site, task.page_pattern.value)
            memory = self.site_memory.setdefault(key, SiteMemory(site=task.site, page_pattern=task.page_pattern.value))
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
        from ai_crawler.spider.runtime.crawl import CrawlTask # 局部导入 CrawlTask
        return list(self.failed)

    def size(self) -> tuple[int, int, int]:
        with self._lock:
            return len(self.pending), len(self.running), len(self.failed)



class CircuitState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class SiteCircuitBreaker:
    FAILURE_THRESHOLD = 5
    BASE_COOLDOWN_SECONDS = 60
    MAX_COOLDOWN_SECONDS = 3600

    def __init__(self):
        self._failure_counts: dict[str, int] = {}
        self._last_failure_time: dict[str, float] = {}
        self._cooldown_end: dict[str, float] = {}
        self._half_open_sites: set[str] = set()
        self._lock = Lock()

    def _get_cooldown(self, failure_count: int) -> float:
        cooldown = self.BASE_COOLDOWN_SECONDS * (2 ** (failure_count - self.FAILURE_THRESHOLD))
        return min(cooldown, self.MAX_COOLDOWN_SECONDS)

    def is_available(self, site: str) -> bool:
        with self._lock:
            if site in self._half_open_sites:
                return True
            if site not in self._cooldown_end:
                return True
            if time.time() >= self._cooldown_end[site]:
                self._half_open_sites.add(site)
                return True
            return False

    def record_failure(self, site: str) -> None:
        with self._lock:
            self._failure_counts[site] = self._failure_counts.get(site, 0) + 1
            self._last_failure_time[site] = time.time()
            self._half_open_sites.discard(site)
            if self._failure_counts[site] >= self.FAILURE_THRESHOLD:
                cooldown = self._get_cooldown(self._failure_counts[site])
                self._cooldown_end[site] = time.time() + cooldown

    def record_success(self, site: str) -> None:
        with self._lock:
            self._failure_counts.pop(site, None)
            self._last_failure_time.pop(site, None)
            self._cooldown_end.pop(site, None)
            self._half_open_sites.discard(site)

    def get_state(self, site: str) -> str:
        with self._lock:
            if site in self._half_open_sites:
                return CircuitState.HALF_OPEN
            if site in self._cooldown_end and time.time() < self._cooldown_end[site]:
                return CircuitState.OPEN
            return CircuitState.CLOSED

    def reset_site(self, site: str) -> None:
        with self._lock:
            self._failure_counts.pop(site, None)
            self._last_failure_time.pop(site, None)
            self._cooldown_end.pop(site, None)
            self._half_open_sites.discard(site)

    def get_cooldown_remaining(self, site: str) -> float:
        with self._lock:
            end = self._cooldown_end.get(site, 0)
            remaining = end - time.time()
            return max(0, remaining)
