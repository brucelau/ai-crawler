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

from ai_crawler.core.strategy import CrawlTask, CrawlStrategy


@dataclass
class StrategyAttempt:
    task_id: str
    url: str
    site: str
    page_pattern: str
    strategy: CrawlStrategy
    block_type: str
    response_snippet: str
    success: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "url": self.url,
            "site": self.site,
            "page_pattern": self.page_pattern,
            "strategy": {
                "tier": getattr(self.strategy, 'tier', 1),
                "render": self.strategy.render.value if hasattr(self.strategy, 'render') else "none",
                "proxy": self.strategy.proxy.value if hasattr(self.strategy, 'proxy') else "thordata_dedicated",
            },
            "block_type": self.block_type,
            "response_snippet": self.response_snippet,
            "success": self.success,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StrategyAttempt":
        from ai_crawler.core.types import ProxyType, RenderType
        strat_data = data.get("strategy", {})
        strategy = CrawlStrategy(
            tier=strat_data.get("tier", 1),
            render=RenderType(strat_data.get("render", "none")),
            proxy=ProxyType(strat_data.get("proxy", "thordata_dedicated")),
        )
        return cls(
            task_id=data["task_id"],
            url=data["url"],
            site=data["site"],
            page_pattern=data["page_pattern"],
            strategy=strategy,
            block_type=data["block_type"],
            response_snippet=data["response_snippet"],
            success=data["success"],
        )


@dataclass
class SiteMemory:
    site: str
    page_pattern: str
    successful_strategies: list[CrawlStrategy] = field(default_factory=list)
    attempt_log: list[StrategyAttempt] = field(default_factory=list)
    llm_tier_cache: dict[str, int] = field(default_factory=dict)
    extraction_method_stats: dict[str, dict[str, int]] = field(default_factory=dict)

    def record_success(self, strategy: CrawlStrategy):
        if strategy not in self.successful_strategies:
            self.successful_strategies.insert(0, strategy)

    def record_extraction_quality(self, method: str, outcome: str, product_count: int) -> None:
        if method not in self.extraction_method_stats:
            self.extraction_method_stats[method] = {"success": 0, "partial": 0, "empty": 0, "error": 0, "total_products": 0}
        stats = self.extraction_method_stats[method]
        if outcome == "success":
            stats["success"] += 1
            stats["total_products"] += product_count
        elif outcome == "partial_content":
            stats["partial"] += 1
            stats["total_products"] += product_count
        elif outcome == "empty_content":
            stats["empty"] += 1
        else:
            stats["error"] += 1

    def get_best_extraction_method(self) -> str | None:
        best_method = None
        best_score = -1
        for method, stats in self.extraction_method_stats.items():
            total = stats["success"] + stats["partial"]
            if total > best_score:
                best_score = total
                best_method = method
        return best_method

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "site": self.site,
            "page_pattern": self.page_pattern,
            "successful_strategies": [
                {
                    "tier": getattr(s, 'tier', 1),
                    "render": s.render.value if hasattr(s, 'render') else "none",
                    "proxy": s.proxy.value if hasattr(s, 'proxy') else "thordata_dedicated",
                }
                for s in self.successful_strategies
            ],
            "attempt_log": [a.to_dict() for a in self.attempt_log],
            "llm_tier_cache": self.llm_tier_cache,
            "extraction_method_stats": self.extraction_method_stats,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SiteMemory":
        from ai_crawler.core.types import ProxyType, RenderType
        strategies = [
            CrawlStrategy(
                tier=s.get("tier", 1),
                render=RenderType(s.get("render", "none")),
                proxy=ProxyType(s.get("proxy", "thordata_dedicated")),
            )
            for s in data.get("successful_strategies", [])
        ]
        attempts = [StrategyAttempt.from_dict(a) for a in data.get("attempt_log", [])]
        return cls(
            site=data["site"],
            page_pattern=data["page_pattern"],
            successful_strategies=strategies,
            attempt_log=attempts,
            llm_tier_cache=data.get("llm_tier_cache", {}),
            extraction_method_stats=data.get("extraction_method_stats", {}),
        )


class SiteMemoryStore:
    def __init__(self, storage_dir: str = "site_memory"):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

    def _site_file(self, site: str) -> str:
        safe_name = site.replace("/", "_").replace("\\", "_")
        return os.path.join(self.storage_dir, f"{safe_name}.json")

    def save(self, memories: dict[tuple[str, str], SiteMemory]) -> None:
        for (site, page_pattern), memory in memories.items():
            if memory.successful_strategies or memory.attempt_log:
                file_path = self._site_file(site)
                data = memory.to_dict()
                with open(file_path, "w") as f:
                    json.dump(data, f)

    def load(self, site: str) -> dict[tuple[str, str], SiteMemory]:
        memories: dict[tuple[str, str], SiteMemory] = {}
        file_path = self._site_file(site)
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                key = (data["site"], data["page_pattern"])
                memories[key] = SiteMemory.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                pass
        return memories


class CrawlQueue:
    def __init__(self, memory_store: SiteMemoryStore | None = None):
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

    def on_success(self, task: CrawlTask, strategy_used: CrawlStrategy) -> None:
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
    ) -> tuple[bool, CrawlStrategy | None]:
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
