"""Tests for CamoufoxPool.fetch — core fetch logic with mocked browser."""

import pytest
from unittest.mock import patch, MagicMock

from ai_crawler.browser.pools.camoufox import CamoufoxPool
from ai_crawler.browser.pools.state import PoolState
from ai_crawler.core.types import CrawlTask, CrawlPolicy, PagePattern, ProxyType, RenderType


class TestCamoufoxPoolFetch:
    """Unit tests for CamoufoxPool.fetch — mocks internal methods."""

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
            render=RenderType.CAMOUFOX,
            proxy=ProxyType.THORDATA_DEDICATED,
            delay_before=(0, 0),
            use_human_scroll=False,
            use_interactive_search=False,
            extra_wait=1.0,
        )

    def _mock_page(self):
        page = MagicMock()
        page.content.return_value = "<html><body>Camoufox Test</body></html>"
        resp = MagicMock()
        resp.status = 200
        page.goto.return_value = resp
        return page

    def test_fetch_basic_page(self, pool_state, task, strategy):
        """Fetch a basic page through Camoufox."""
        mock_page = self._mock_page()
        pool = CamoufoxPool(pool_state)

        with patch.object(pool, "_get_camoufox_browser", return_value=MagicMock()), \
             patch.object(pool, "_install_ad_script_blocking"), \
             patch.object(pool, "_wait_for_page_ready"), \
             patch.object(pool, "_release_camoufox_browser"):
            mock_browser = MagicMock()
            mock_browser.new_page.return_value = mock_page
            pool._get_camoufox_browser.return_value = mock_browser

            content, status, page = pool.fetch(task, strategy)

            assert content == "<html><body>Camoufox Test</body></html>"
            assert status == 200
            assert page is mock_page
            mock_page.goto.assert_called_once()
            mock_page.content.assert_called_once()

    def test_fetch_with_error_returns_empty(self, pool_state, task, strategy):
        """When fetch fails, returns empty content."""
        bad_page = MagicMock()
        bad_page.goto.side_effect = RuntimeError("Connection refused")
        pool = CamoufoxPool(pool_state)

        with patch.object(pool, "_get_camoufox_browser", return_value=MagicMock()), \
             patch.object(pool, "_install_ad_script_blocking"), \
             patch.object(pool, "_release_camoufox_browser"):
            mock_browser = MagicMock()
            mock_browser.new_page.return_value = bad_page
            pool._get_camoufox_browser.return_value = mock_browser

            content, status, page = pool.fetch(task, strategy)

            assert content == ""
            assert status is None
            assert page is None

    def test_fetch_with_human_scroll(self, pool_state, task, strategy):
        """Fetch with human_scroll enabled."""
        strategy.use_human_scroll = True
        mock_page = self._mock_page()
        pool = CamoufoxPool(pool_state)

        with patch.object(pool, "_get_camoufox_browser", return_value=MagicMock()), \
             patch.object(pool, "_install_ad_script_blocking"), \
             patch.object(pool, "_wait_for_page_ready"), \
             patch.object(pool, "_human_scroll") as mock_human_scroll, \
             patch.object(pool, "_release_camoufox_browser"):
            mock_browser = MagicMock()
            mock_browser.new_page.return_value = mock_page
            pool._get_camoufox_browser.return_value = mock_browser

            content, status, _ = pool.fetch(task, strategy)
            assert content == "<html><body>Camoufox Test</body></html>"
            mock_human_scroll.assert_called_once_with(mock_page)

    def test_navigation_timeout_default(self, pool_state, task, strategy):
        """Default navigation timeout is page_load_timeout * 1000 ms."""
        pool = CamoufoxPool(pool_state, page_load_timeout=30.0)
        timeout = pool._navigation_timeout_ms(task, strategy)
        assert timeout == 30000

    def test_navigation_timeout_search_pattern(self, pool_state, strategy):
        """Search pattern gets minimum 20s timeout."""
        task = CrawlTask(
            url="https://example.com/search?q=test",
            site="example",
            page_pattern=PagePattern.SEARCH,
        )
        pool = CamoufoxPool(pool_state, page_load_timeout=5.0)
        timeout = pool._navigation_timeout_ms(task, strategy)
        assert timeout >= 20000

    def test_delay_before_applied(self, pool_state, task):
        """When delay_before > 0, sleep is called before fetch."""
        strategy = CrawlPolicy(delay_before=(0.1, 0.2))
        pool = CamoufoxPool(pool_state)
        with patch("time.sleep") as mock_sleep, \
             patch.object(pool, "_get_camoufox_browser", side_effect=RuntimeError("stop early")):
            try:
                pool.fetch(task, strategy)
            except RuntimeError:
                pass
            mock_sleep.assert_called()

    def test_is_camoufox_browser_healthy_connected(self, pool_state):
        """Healthy browser reports True when connected."""
        pool = CamoufoxPool(pool_state)
        mock_browser = MagicMock()
        mock_browser.is_connected.return_value = True
        assert pool._is_camoufox_browser_healthy(mock_browser) is True

    def test_is_camoufox_browser_healthy_disconnected(self, pool_state):
        """Unhealthy browser reports False when disconnected."""
        pool = CamoufoxPool(pool_state)
        mock_browser = MagicMock()
        mock_browser.is_connected.return_value = False
        assert pool._is_camoufox_browser_healthy(mock_browser) is False

    def test_is_camoufox_browser_healthy_exception(self, pool_state):
        """Browser that raises on health check is unhealthy."""
        pool = CamoufoxPool(pool_state)
        mock_browser = MagicMock()
        mock_browser.is_connected.side_effect = RuntimeError("boom")
        assert pool._is_camoufox_browser_healthy(mock_browser) is False
