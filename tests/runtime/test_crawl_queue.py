"""Tests for Queue — task queue management with adaptive strategy."""

import pytest
from ai_crawler.crawl.queue import Queue
from ai_crawler.core.types import CrawlTask, CrawlPolicy, PagePattern


def _make_task(site="amazon", url="https://www.amazon.com/s?k=test"):
    return CrawlTask(url=url, site=site, page_pattern=PagePattern.SEARCH)


class TestQueueBasics:
    def test_empty_queue_size(self):
        queue = Queue()
        pending, running, failed = queue.size()
        assert pending == 0
        assert running == 0
        assert failed == 0

    def test_enqueue_increases_pending(self):
        queue = Queue()
        queue.enqueue([_make_task()])
        pending, _, _ = queue.size()
        assert pending == 1

    def test_dequeue_returns_task_and_moves_to_running(self):
        queue = Queue()
        task = _make_task()
        queue.enqueue([task])
        dequeued = queue.dequeue()
        assert dequeued is task
        _, running, _ = queue.size()
        assert running == 1

    def test_dequeue_empty_returns_none(self):
        queue = Queue()
        assert queue.dequeue() is None

    def test_dequeue_exhausts_pending(self):
        queue = Queue()
        queue.enqueue([_make_task()])
        queue.dequeue()
        pending, _, _ = queue.size()
        assert pending == 0


class TestQueueOnSuccess:
    def test_on_success_removes_from_running(self):
        queue = Queue()
        task = _make_task()
        queue.enqueue([task])
        queue.dequeue()
        task.strategy = CrawlPolicy()
        queue.on_success(task, task.strategy)
        _, running, _ = queue.size()
        assert running == 0

    def test_on_success_records_in_site_memory(self):
        queue = Queue()
        task = _make_task()
        queue.enqueue([task])
        queue.dequeue()
        task.strategy = CrawlPolicy()
        queue.on_success(task, task.strategy)
        memory = queue.site_memory.get((task.site, task.page_pattern.value))
        assert memory is not None


class TestQueueOnFailure:
    def test_on_failure_requeues_when_attempts_remain(self):
        queue = Queue()
        task = _make_task()
        task.max_attempts = 5
        task.attempt_count = 1
        queue.enqueue([task])
        queue.dequeue()
        exhausted = queue.on_failure(task, "http_403", "")
        assert exhausted is False
        pending, _, _ = queue.size()
        assert pending == 1

    def test_on_failure_marks_exhausted_when_max_attempts_reached(self):
        queue = Queue()
        task = _make_task()
        task.max_attempts = 8
        task.attempt_count = 8
        queue.enqueue([task])
        queue.dequeue()
        exhausted = queue.on_failure(task, "http_403", "")
        assert exhausted is True

    def test_on_failure_moves_to_failed_when_exhausted(self):
        queue = Queue()
        task = _make_task()
        task.max_attempts = 3
        task.attempt_count = 3
        queue.enqueue([task])
        queue.dequeue()
        queue.on_failure(task, "http_403", "")
        _, _, failed = queue.size()
        assert failed == 1

    def test_on_failure_increments_fail_count(self):
        queue = Queue()
        task = _make_task()
        queue.enqueue([task])
        queue.dequeue()
        queue.on_failure(task, "http_403", "")
        assert task.fail_count == 1

    def test_on_failure_records_attempt_in_site_memory(self):
        queue = Queue()
        task = _make_task()
        task.max_attempts = 3
        task.attempt_count = 3
        queue.enqueue([task])
        queue.dequeue()
        queue.on_failure(task, "http_403", "Access denied")
        memory = queue.site_memory.get((task.site, task.page_pattern.value))
        assert len(memory.attempt_log) == 1
        assert memory.attempt_log[0].block_type == "http_403"
        assert memory.attempt_log[0].response_snippet == "Access denied"


class TestQueueRetryFailed:
    def test_retry_failed_moves_to_pending(self):
        queue = Queue()
        task = _make_task()
        task.max_attempts = 3
        task.attempt_count = 3
        task.fail_count = 1
        queue.enqueue([task])
        queue.dequeue()
        queue.on_failure(task, "http_403", "")
        queue.retry_failed()
        pending, _, _ = queue.size()
        assert pending == 1

    def test_retry_failed_does_not_retry_task_with_fail_count_3(self):
        queue = Queue()
        task = _make_task()
        task.max_attempts = 3
        task.attempt_count = 3
        task.fail_count = 3
        queue.enqueue([task])
        queue.dequeue()
        queue.on_failure(task, "http_403", "")
        retried = queue.retry_failed()
        assert len(retried) == 0

    def test_retry_failed_removes_from_failed_list(self):
        queue = Queue()
        task = _make_task()
        task.max_attempts = 3
        task.attempt_count = 3
        task.fail_count = 1
        queue.enqueue([task])
        queue.dequeue()
        queue.on_failure(task, "http_403", "")
        queue.retry_failed()
        _, _, failed = queue.size()
        assert failed == 0


class TestQueueGetFailedTasks:
    def test_get_failed_tasks_returns_list(self):
        queue = Queue()
        task = _make_task()
        task.max_attempts = 3
        task.attempt_count = 3
        queue.enqueue([task])
        queue.dequeue()
        queue.on_failure(task, "http_403", "")
        failed = queue.get_failed_tasks()
        assert len(failed) == 1
        assert failed[0] is task

    def test_get_failed_tasks_returns_copy(self):
        queue = Queue()
        task = _make_task()
        task.max_attempts = 3
        task.attempt_count = 3
        queue.enqueue([task])
        queue.dequeue()
        queue.on_failure(task, "http_403", "")
        failed1 = queue.get_failed_tasks()
        queue.retry_failed()
        failed2 = queue.get_failed_tasks()
        assert len(failed1) == 1
        assert len(failed2) == 0
