"""Tests for CrawlQueue - task queue management and scheduling."""

import pytest
from ai_crawler.core.engine.queue import CrawlQueue, StrategyAttempt, SiteMemory
from ai_crawler.core.strategy import CrawlTask, CrawlStrategy, ProxyType, RenderType


class TestCrawlQueueBasics:
    """CrawlQueue basic enqueue/dequeue operations."""

    def test_empty_queue_size(self):
        queue = CrawlQueue()
        pending, running, failed = queue.size()
        assert pending == 0
        assert running == 0
        assert failed == 0

    def test_enqueue_increases_pending(self):
        queue = CrawlQueue()
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        queue.enqueue([task])
        pending, _, _ = queue.size()
        assert pending == 1

    def test_dequeue_returns_task_and_moves_to_running(self):
        queue = CrawlQueue()
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        queue.enqueue([task])
        dequeued = queue.dequeue()
        assert dequeued is task
        _, running, _ = queue.size()
        assert running == 1

    def test_dequeue_empty_returns_none(self):
        queue = CrawlQueue()
        result = queue.dequeue()
        assert result is None

    def test_dequeue_exhausts_pending(self):
        queue = CrawlQueue()
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        queue.enqueue([task])
        queue.dequeue()
        pending, _, _ = queue.size()
        assert pending == 0


class TestCrawlQueueOnSuccess:
    """CrawlQueue.on_success() should remove task from running."""

    def test_on_success_removes_from_running(self):
        queue = CrawlQueue()
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        queue.enqueue([task])
        queue.dequeue()
        strategy = task.strategies[0]
        queue.on_success(task, strategy)
        _, running, _ = queue.size()
        assert running == 0

    def test_on_success_records_in_site_memory(self):
        queue = CrawlQueue()
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        queue.enqueue([task])
        queue.dequeue()
        strategy = task.strategies[0]
        queue.on_success(task, strategy)
        memory = queue.site_memory.get((task.site, task.page_pattern.value))
        assert memory is not None


class TestCrawlQueueOnFailure:
    """CrawlQueue.on_failure() should handle strategy exhaustion."""

    def test_on_failure_advances_strategy_when_strategies_remain(self):
        queue = CrawlQueue()
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        initial_index = task.current_index
        queue.enqueue([task])
        queue.dequeue()
        needs_llm, next_strategy = queue.on_failure(task, "http_403", "")
        assert needs_llm is False
        assert next_strategy is not None
        assert task.current_index == initial_index + 1

    def test_on_failure_requeues_when_strategies_remain(self):
        queue = CrawlQueue()
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        queue.enqueue([task])
        queue.dequeue()
        queue.on_failure(task, "http_403", "")
        pending, _, _ = queue.size()
        assert pending == 1

    def test_on_failure_marks_exhausted_when_no_strategies_left(self):
        queue = CrawlQueue()
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        task.current_index = len(task.strategies)
        queue.enqueue([task])
        queue.dequeue()
        needs_llm, _ = queue.on_failure(task, "http_403", "")
        assert needs_llm is True

    def test_on_failure_moves_to_failed_when_exhausted(self):
        queue = CrawlQueue()
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        task.current_index = len(task.strategies)
        queue.enqueue([task])
        queue.dequeue()
        queue.on_failure(task, "http_403", "")
        _, _, failed = queue.size()
        assert failed == 1

    def test_on_failure_increments_fail_count(self):
        queue = CrawlQueue()
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        queue.enqueue([task])
        queue.dequeue()
        queue.on_failure(task, "http_403", "")
        assert task.fail_count == 1

    def test_on_failure_records_attempt_in_site_memory(self):
        queue = CrawlQueue()
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        task.current_index = len(task.strategies)
        queue.enqueue([task])
        queue.dequeue()
        queue.on_failure(task, "http_403", "Access denied")
        memory = queue.site_memory.get((task.site, task.page_pattern.value))
        assert len(memory.attempt_log) == 1
        assert memory.attempt_log[0].block_type == "http_403"
        assert memory.attempt_log[0].response_snippet == "Access denied"


class TestCrawlQueueRetryFailed:
    """CrawlQueue.retry_failed() should reset eligible failed tasks."""

    def test_retry_failed_resets_task_index(self):
        queue = CrawlQueue()
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        task.current_index = len(task.strategies)
        task.fail_count = 1
        queue.enqueue([task])
        queue.dequeue()
        queue.on_failure(task, "http_403", "")
        retried = queue.retry_failed()
        assert len(retried) == 1
        assert retried[0].current_index == 0

    def test_retry_failed_moves_to_pending(self):
        queue = CrawlQueue()
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        task.current_index = len(task.strategies)
        task.fail_count = 1
        queue.enqueue([task])
        queue.dequeue()
        queue.on_failure(task, "http_403", "")
        queue.retry_failed()
        pending, _, _ = queue.size()
        assert pending == 1

    def test_retry_failed_does_not_retry_task_with_fail_count_3(self):
        queue = CrawlQueue()
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        task.current_index = len(task.strategies)
        task.fail_count = 3
        queue.enqueue([task])
        queue.dequeue()
        queue.on_failure(task, "http_403", "")
        retried = queue.retry_failed()
        assert len(retried) == 0

    def test_retry_failed_removes_from_failed_list(self):
        queue = CrawlQueue()
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        task.current_index = len(task.strategies)
        task.fail_count = 1
        queue.enqueue([task])
        queue.dequeue()
        queue.on_failure(task, "http_403", "")
        queue.retry_failed()
        _, _, failed = queue.size()
        assert failed == 0


class TestCrawlQueueGetFailedTasks:
    """CrawlQueue.get_failed_tasks() should return all failed tasks."""

    def test_get_failed_tasks_returns_list(self):
        queue = CrawlQueue()
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        task.current_index = len(task.strategies)
        queue.enqueue([task])
        queue.dequeue()
        queue.on_failure(task, "http_403", "")
        failed = queue.get_failed_tasks()
        assert len(failed) == 1
        assert failed[0] is task

    def test_get_failed_tasks_returns_copy(self):
        queue = CrawlQueue()
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        task.current_index = len(task.strategies)
        queue.enqueue([task])
        queue.dequeue()
        queue.on_failure(task, "http_403", "")
        failed1 = queue.get_failed_tasks()
        queue.retry_failed()
        failed2 = queue.get_failed_tasks()
        assert len(failed1) == 1
        assert len(failed2) == 0
