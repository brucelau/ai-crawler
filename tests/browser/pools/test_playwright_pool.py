"""Tests for PlaywrightPool.fetch — core fetch logic with mocked browser."""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from ai_crawler.browser.pools.playwright import PlaywrightPool
from ai_crawler.browser.pools.state import PoolState
from ai_crawler.core.types import CrawlTask, CrawlPolicy, PagePattern, ProxyType, RenderType


class TestPlaywrightPoolFetch:
    """Unit tests for PlaywrightPool.fetch — mocks internal methods to avoid
    real browser imports."""

    @pytest.fixture
    def pool_state(self):
        return PoolState()

    @pytest.fixture
    def task(self):
        return CrawlTask(
            url="https://example.com/search?q=test",
            site="example",
            page_pattern=PagePattern.SEARCH,
            task_id="test-001",
        )

    @pytest.fixture
    def strategy(self):
        return CrawlPolicy(
            render=RenderType.PLAYWRIGHT,
            proxy=ProxyType.THORDATA_DEDICATED,
            delay_before=(0, 0),
            use_human_scroll=False,
            use_interactive_search=False,
            extra_wait=1.0,
        )

    def _mock_page(self):
        page = MagicMock()
        page.content.return_value = "<html><body>Test</body></html>"
        resp = MagicMock()
        resp.status = 200
        page.goto.return_value = resp
        type(page).viewport_size = PropertyMock(return_value={"width": 1920, "height": 1080})
        return page

    def test_fetch_basic_page(self, pool_state, task, strategy):
        """Fetch a basic page without human scroll or interactive search."""
        mock_page = self._mock_page()
        pool = PlaywrightPool(pool_state)

        with patch.object(pool, "_get_playwright_browser", return_value=MagicMock()), \
             patch.object(pool, "_get_playwright_context", return_value=MagicMock()), \
             patch.object(pool, "_install_ad_script_blocking"), \
             patch.object(pool, "_wait_for_page_ready"), \
             patch.object(pool, "_human_scroll"):
            mock_ctx = MagicMock()
            mock_ctx.new_page.return_value = mock_page
            pool._get_playwright_context.return_value = mock_ctx

            content, status, page = pool.fetch(task, strategy)

            assert content == "<html><body>Test</body></html>"
            assert status == 200
            assert page is mock_page
            mock_page.goto.assert_called_once()
            mock_page.content.assert_called_once()

    def test_fetch_with_human_scroll(self, pool_state, task, strategy):
        """Fetch with human_scroll enabled triggers scroll behavior."""
        strategy.use_human_scroll = True
        mock_page = self._mock_page()
        pool = PlaywrightPool(pool_state)

        with patch.object(pool, "_get_playwright_browser", return_value=MagicMock()), \
             patch.object(pool, "_get_playwright_context", return_value=MagicMock()), \
             patch.object(pool, "_install_ad_script_blocking"), \
             patch.object(pool, "_wait_for_page_ready"), \
             patch.object(pool, "_human_scroll") as mock_human_scroll:
            mock_ctx = MagicMock()
            mock_ctx.new_page.return_value = mock_page
            pool._get_playwright_context.return_value = mock_ctx

            content, status, _ = pool.fetch(task, strategy)

            assert content == "<html><body>Test</body></html>"
            assert status == 200
            mock_human_scroll.assert_called_once_with(mock_page)

    def test_fetch_with_error_returns_empty(self, pool_state, task, strategy):
        """When page.goto raises, fetch returns empty content."""
        bad_page = MagicMock()
        bad_page.goto.side_effect = RuntimeError("Connection refused")
        pool = PlaywrightPool(pool_state)

        with patch.object(pool, "_get_playwright_browser", return_value=MagicMock()), \
             patch.object(pool, "_get_playwright_context", return_value=MagicMock()), \
             patch.object(pool, "_install_ad_script_blocking"):
            mock_ctx = MagicMock()
            mock_ctx.new_page.return_value = bad_page
            pool._get_playwright_context.return_value = mock_ctx

            content, status, page = pool.fetch(task, strategy)

            assert content == ""
            assert status is None
            assert page is None

    def test_navigation_timeout_default(self, pool_state, task, strategy):
        """Default navigation timeout is page_load_timeout * 1000 ms."""
        pool = PlaywrightPool(pool_state, page_load_timeout=30.0)
        timeout = pool._navigation_timeout_ms(task, strategy)
        assert timeout == 30000

    def test_navigation_timeout_search_pattern(self, pool_state, strategy):
        """Search pattern gets minimum 20s timeout."""
        task = CrawlTask(
            url="https://example.com/search?q=test",
            site="example",
            page_pattern=PagePattern.SEARCH,
        )
        pool = PlaywrightPool(pool_state, page_load_timeout=5.0)
        timeout = pool._navigation_timeout_ms(task, strategy)
        assert timeout >= 20000

    def test_navigation_timeout_target_search(self, pool_state, strategy):
        """target/amazon search pattern gets minimum 30s timeout."""
        task = CrawlTask(
            url="https://www.target.com/s?q=test",
            site="target",
            page_pattern=PagePattern.SEARCH,
        )
        pool = PlaywrightPool(pool_state, page_load_timeout=5.0)
        timeout = pool._navigation_timeout_ms(task, strategy)
        assert timeout >= 30000

    def test_wait_for_page_ready_with_selector(self, pool_state, strategy):
        """wait_for_page_ready uses wait_selector when configured."""
        strategy.wait_selector = ".results"
        pool = PlaywrightPool(pool_state)
        mock_page = MagicMock()
        pool._wait_for_page_ready(mock_page, strategy)
        mock_page.wait_for_selector.assert_called_once()
        call_args = mock_page.wait_for_selector.call_args
        assert call_args[0][0] == ".results"

    def test_wait_for_page_ready_fallback(self, pool_state, strategy):
        """wait_for_page_ready falls back to timeout when no selector."""
        pool = PlaywrightPool(pool_state)
        mock_page = MagicMock()
        pool._wait_for_page_ready(mock_page, strategy)
        mock_page.wait_for_timeout.assert_called_once()

    def test_install_ad_script_blocking_no_route(self, pool_state):
        """Does not install route handler when page has no route method."""
        pool = PlaywrightPool(pool_state)
        mock_page = MagicMock(spec=[])
        pool._install_ad_script_blocking(mock_page)

    def test_delay_before_applied(self, pool_state, task):
        """When delay_before > 0, sleep is called before fetch."""
        strategy = CrawlPolicy(delay_before=(0.1, 0.2))
        pool = PlaywrightPool(pool_state)
        with patch("time.sleep") as mock_sleep, \
             patch.object(pool, "_get_playwright_browser", side_effect=RuntimeError("stop early")):
            try:
                pool.fetch(task, strategy)
            except RuntimeError:
                pass
            mock_sleep.assert_called()

    def test_navigation_timeout_with_extra_wait(self, pool_state, task, strategy):
        """extra_wait boosts navigation timeout."""
        strategy.extra_wait = 5.0
        pool = PlaywrightPool(pool_state, page_load_timeout=10.0)
        timeout = pool._navigation_timeout_ms(task, strategy)
        assert timeout >= 20000
