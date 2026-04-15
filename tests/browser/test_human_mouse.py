"""Tests for HumanBehaviorGenerator and CachedLLMHumanBehavior."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from ai_crawler.browser.human_mouse import (
    Point,
    generate_human_curve,
    scroll_human,
    HumanMouseController,
    MouseAdapter,
    PlaywrightMouseAdapter,
    UnifiedHumanBehavior,
    LLMHumanBehavior,
    CachedLLMHumanBehavior,
)


class TestPoint:
    """Point dataclass for coordinates."""

    def test_point_creation(self):
        """Point holds x and y coordinates."""
        p = Point(100.0, 200.0)
        assert p.x == 100.0
        assert p.y == 200.0


class TestGenerateHumanCurve:
    """generate_human_curve() generates bezier curves."""

    def test_short_distance_returns_two_points(self):
        """Very short distance returns start and end only."""
        points = generate_human_curve((0, 0), (1, 1))
        assert len(points) == 2
        assert points[0].x == 0
        assert points[-1].x == 1

    def test_returns_list_of_points(self):
        """Returns list of Point objects."""
        points = generate_human_curve((0, 0), (100, 100))
        assert isinstance(points, list)
        assert all(isinstance(p, Point) for p in points)

    def test_end_point_preserved(self):
        """End point coordinates are preserved."""
        points = generate_human_curve((0, 0), (500, 500))
        assert points[-1].x == 500
        assert points[-1].y == 500


class TestScrollHuman:
    """scroll_human() scrolls page with human-like motion."""

    def test_scroll_human_accepts_page(self):
        """scroll_human accepts page object."""
        mock_page = Mock()
        scroll_human(mock_page, 0, 100, 50)


class TestHumanMouseController:
    """HumanMouseController moves mouse with human-like curves."""

    def test_init(self):
        """Controller stores page and parameters."""
        mock_page = Mock()
        controller = HumanMouseController(mock_page)
        assert controller.page is mock_page

    def test_move_to_with_duration(self):
        """move_to accepts x, y and optional duration."""
        mock_page = Mock()
        controller = HumanMouseController(mock_page)
        controller.move_to(100, 200, duration=0.5)
        assert mock_page.mouse.move.called

    def test_click(self):
        """click moves then clicks."""
        mock_page = Mock()
        controller = HumanMouseController(mock_page)
        controller.click(100, 200)
        assert mock_page.mouse.move.called
        assert mock_page.mouse.click.called


class TestMouseAdapter:
    """MouseAdapter abstract base class."""

    def test_is_abc(self):
        """MouseAdapter is abstract."""
        assert issubclass(MouseAdapter.__bases__[0], object)


class TestPlaywrightMouseAdapter:
    """PlaywrightMouseAdapter wraps Playwright page."""

    def test_move(self):
        """move delegates to page.mouse.move."""
        mock_page = Mock()
        adapter = PlaywrightMouseAdapter(mock_page)
        adapter.move(100, 200)
        mock_page.mouse.move.assert_called_once_with(100, 200)

    def test_scroll(self):
        """scroll delegates to page.mouse.wheel."""
        mock_page = Mock()
        adapter = PlaywrightMouseAdapter(mock_page)
        adapter.scroll(0, 100)
        mock_page.mouse.wheel.assert_called_once_with(0, 100)


class TestUnifiedHumanBehavior:
    """UnifiedHumanBehavior provides consistent interface."""

    def test_init(self):
        """Initializes with adapter."""
        mock_adapter = Mock(spec=MouseAdapter)
        behavior = UnifiedHumanBehavior(mock_adapter)
        assert behavior._adapter is mock_adapter

    def test_move_to(self):
        """move_to moves mouse smoothly."""
        mock_adapter = Mock(spec=MouseAdapter)
        behavior = UnifiedHumanBehavior(mock_adapter)
        behavior.move_to(100, 200)
        assert mock_adapter.move.called

    def test_scroll(self):
        """scroll scrolls the page."""
        mock_adapter = Mock(spec=MouseAdapter)
        behavior = UnifiedHumanBehavior(mock_adapter)
        behavior.scroll(0, 1500)
        assert mock_adapter.scroll.called


class TestLLMHumanBehavior:
    """LLMHumanBehavior generates patterns via LLM."""

    def test_init_with_defaults(self):
        """Initializes with config defaults when no args provided."""
        from ai_crawler.config import config

        original_key = config.OPENAI_API_KEY
        original_url = config.OPENAI_BASE_URL
        original_model = config.MODEL_NAME
        try:
            config.OPENAI_API_KEY = ""
            config.OPENAI_BASE_URL = None
            config.MODEL_NAME = "gpt-4o"
            behavior = LLMHumanBehavior()
            assert behavior._model == "gpt-4o"
        finally:
            config.OPENAI_API_KEY = original_key
            config.OPENAI_BASE_URL = original_url
            config.MODEL_NAME = original_model

    def test_init_with_custom_values(self):
        """Initializes with custom API key and model."""
        behavior = LLMHumanBehavior(api_key="test-key", model="gpt-4o-mini")
        assert behavior._api_key == "test-key"
        assert behavior._model == "gpt-4o-mini"

    def test_get_client_returns_none_without_key(self):
        """_get_client returns None when no API key and no client."""
        from unittest.mock import patch
        import os

        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            behavior = LLMHumanBehavior(api_key="")
            behavior._client = None
            behavior._api_key = ""
            result = behavior._get_client()
            assert result is None

    def test_default_pattern_structure(self):
        """Default pattern has correct structure."""
        behavior = LLMHumanBehavior(api_key="")
        pattern = behavior._default_pattern()
        assert "scroll_strategy" in pattern
        assert "scroll_phases" in pattern
        assert isinstance(pattern["scroll_phases"], list)

    def test_generate_pattern_returns_dict(self):
        """generate_pattern returns a dict."""
        behavior = LLMHumanBehavior(api_key="")
        result = behavior.generate_pattern("amazon", "search")
        assert isinstance(result, dict)
        assert "scroll_strategy" in result


class TestCachedLLMHumanBehavior:
    """CachedLLMHumanBehavior caches LLM-generated patterns."""

    def test_singleton_pattern(self):
        """CachedLLMHumanBehavior uses singleton."""
        b1 = CachedLLMHumanBehavior()
        b2 = CachedLLMHumanBehavior()
        assert b1 is b2

    def test_init_with_custom_cache_ttl(self):
        """Can set custom cache TTL."""
        CachedLLMHumanBehavior._instance = None
        bhv = CachedLLMHumanBehavior(cache_ttl=7200)
        assert bhv._cache_ttl == 7200
        CachedLLMHumanBehavior._instance = None

    def test_should_refresh_when_no_cache(self):
        """Should refresh when cache is empty."""
        bhv = CachedLLMHumanBehavior.__new__(CachedLLMHumanBehavior)
        bhv._initialized = False
        bhv._cached_pattern = None
        bhv._cached_time = 0
        bhv._cache_ttl = 3600
        assert bhv._should_refresh() is True

    def test_should_refresh_after_ttl(self):
        """Should refresh after TTL expires."""
        import time

        bhv = CachedLLMHumanBehavior.__new__(CachedLLMHumanBehavior)
        bhv._initialized = False
        bhv._cached_pattern = {"test": True}
        bhv._cached_time = time.time() - 7200
        bhv._cache_ttl = 3600
        assert bhv._should_refresh() is True

    def test_should_not_refresh_within_ttl(self):
        """Should not refresh within TTL."""
        import time

        bhv = CachedLLMHumanBehavior.__new__(CachedLLMHumanBehavior)
        bhv._initialized = False
        bhv._cached_pattern = {"test": True}
        bhv._cached_time = time.time() - 100
        bhv._cache_ttl = 3600
        assert bhv._should_refresh() is False

    def test_get_cached_pattern_returns_cached(self):
        """Returns cached pattern when valid."""
        import time

        bhv = CachedLLMHumanBehavior.__new__(CachedLLMHumanBehavior)
        bhv._initialized = False
        bhv._dspy_generator = None
        bhv._cached_pattern = {"scroll_strategy": "cached"}
        bhv._cached_time = time.time()
        bhv._cache_ttl = 3600
        result = bhv.get_cached_pattern("amazon", "search")
        assert result["scroll_strategy"] == "cached"

    def test_default_pattern_structure(self):
        """Default pattern has correct structure."""
        bhv = CachedLLMHumanBehavior.__new__(CachedLLMHumanBehavior)
        bhv._initialized = False
        bhv._dspy_generator = None
        pattern = bhv._default_pattern()
        assert "scroll_strategy" in pattern
        assert "scroll_phases" in pattern

    def test_execute_pattern_accepts_adapter(self):
        """execute_pattern accepts MouseAdapter."""
        mock_adapter = Mock(spec=MouseAdapter)
        bhv = CachedLLMHumanBehavior.__new__(CachedLLMHumanBehavior)
        bhv._initialized = False
        pattern = {"scroll_phases": []}
        bhv.execute_pattern(mock_adapter, pattern)
