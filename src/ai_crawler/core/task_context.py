from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ai_crawler.core.types import CrawlTask, CrawlStrategy
from ai_crawler.core.engine.results import CrawlResult


@dataclass
class Event:
    type: str
    success: bool
    strategy: CrawlStrategy | None = None
    block_type: str = ""
    latency_ms: float = 0
    html_size: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class TaskContext:
    def __init__(self, task: CrawlTask):
        self.task = task
        self._events: list[Event] = []
        self._tried_strategies: list[CrawlStrategy] = []
        self._attempt_count: int = 0
        self._result: CrawlResult | None = None

    @property
    def events(self) -> list[Event]:
        return self._events

    @property
    def tried_strategies(self) -> list[CrawlStrategy]:
        return self._tried_strategies

    @property
    def attempt_count(self) -> int:
        return self._attempt_count

    @property
    def result(self) -> CrawlResult | None:
        return self._result

    def add_event(self, event: Event):
        self._events.append(event)

    def add_tried_strategy(self, strategy: CrawlStrategy):
        self._tried_strategies.append(strategy)

    def increment_attempt(self):
        self._attempt_count += 1

    def set_result(self, result: CrawlResult):
        self._result = result