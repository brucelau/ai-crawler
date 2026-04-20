"""Tests for CrawlTask - task creation and strategy management."""

import pytest
from ai_crawler.core.strategy import CrawlTask, PagePattern, CrawlStrategy, ProxyType, RenderType


class TestCrawlTaskCreate:
    """CrawlTask.create() should build task with correct pattern and strategies."""

    def test_amazon_search_url_detects_search_pattern(self):
        task = CrawlTask.create("https://www.amazon.com/s?k=inflatable", "amazon")
        assert task.page_pattern == PagePattern.SEARCH
        assert task.site == "amazon"

    def test_amazon_detail_url_detects_detail_pattern(self):
        task = CrawlTask.create("https://www.amazon.com/dp/B08N5WRWNW", "amazon")
        assert task.page_pattern == PagePattern.DETAIL

    def test_unknown_url_detects_unknown_pattern(self):
        task = CrawlTask.create("https://www.amazon.com/weird/path", "amazon")
        assert task.page_pattern == PagePattern.UNKNOWN

    def test_search_url_gets_search_strategies(self):
        task = CrawlTask.create("https://www.amazon.com/s?k=inflatable", "amazon")
        assert len(task.strategies) > 0
        assert task.current_index == 0

    def test_detail_url_gets_detail_strategies(self):
        task = CrawlTask.create("https://www.amazon.com/dp/B08N5WRWNW", "amazon")
        assert len(task.strategies) > 0
        assert task.current_index == 0

    def test_unknown_pattern_gets_fallback_strategies(self):
        task = CrawlTask.create("https://www.amazon.com/unknown", "amazon")
        assert len(task.strategies) > 0

    def test_unknown_site_gets_unknown_pattern(self):
        task = CrawlTask.create("https://unknown.com/s?k=test", "unknownsite")
        assert task.page_pattern == PagePattern.UNKNOWN

    def test_task_has_uuid(self):
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        assert task.task_id is not None
        assert len(task.task_id) == 8

    def test_tasks_have_unique_ids(self):
        t1 = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        t2 = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        assert t1.task_id != t2.task_id

    def test_unknown_site_still_has_default_strategy(self):
        task = CrawlTask.create("https://example.com/test", "unknownsite")
        assert len(task.strategies) == 10
        assert task.strategies[0].render == RenderType.NONE
        assert task.strategies[0].proxy == ProxyType.THORDATA_DEDICATED

    def test_unknown_site_fallback_to_manual_strategies(self):
        task = CrawlTask.create("https://example.com/test", "unknownsite", use_auto_strategies=False)
        assert len(task.strategies) == 1
        assert task.strategies[0] == CrawlStrategy()


class TestCrawlTaskLifecycle:
    """CrawlTask lifecycle methods should manage strategy progression."""

    def test_current_strategy_returns_current(self):
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        strategy = task.current_strategy()
        assert strategy is not None
        assert isinstance(strategy, CrawlStrategy)

    def test_current_strategy_returns_none_when_exhausted(self):
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        strategies_count = len(task.strategies)
        task.current_index = strategies_count
        assert task.current_strategy() is None

    def test_exhausted_false_initially(self):
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        assert task.exhausted() is False

    def test_exhausted_true_after_all_strategies_used(self):
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        task.current_index = len(task.strategies)
        assert task.exhausted() is True

    def test_advance_moves_to_next_strategy(self):
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        first = task.current_strategy()
        task.advance()
        second = task.current_strategy()
        assert first != second

    def test_advance_beyond_strategies_returns_none(self):
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        task.current_index = len(task.strategies)
        task.advance()
        assert task.current_strategy() is None

    def test_add_strategy_front_inserts_before_current(self):
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        original = task.strategies[0]
        new_strategy = CrawlStrategy(proxy=ProxyType.THORDATA_ANY)
        task.add_strategy_front(new_strategy)
        assert task.strategies[0] == new_strategy
        assert task.strategies[1] == original

    def test_add_strategy_next_inserts_after_current(self):
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        original = task.strategies[0]
        new_strategy = CrawlStrategy(render=RenderType.CAMOUFOX)
        task.add_strategy_next(new_strategy)
        assert task.strategies[0] == original
        assert task.strategies[1] == new_strategy

    def test_reset_restarts_from_beginning(self):
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        task.current_index = len(task.strategies)
        task.fail_count = 5
        task.reset()
        assert task.current_index == 0
        assert task.fail_count == 0

    def test_attempt_summary_contains_fields(self):
        task = CrawlTask.create("https://www.amazon.com/s?k=test", "amazon")
        summary = task.attempt_summary()
        assert summary["task_id"] == task.task_id
        assert summary["url"] == task.url
        assert summary["site"] == task.site
        assert summary["pattern"] == task.page_pattern.value
        assert summary["current_index"] == 0
        assert summary["total_strategies"] == len(task.strategies)
        assert summary["fail_count"] == 0
