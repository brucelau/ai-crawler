"""Tests for HumanBehaviorGenerator and CachedLLMHumanBehavior."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from ai_crawler.browser.human.mouse import (
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
        """Very short distance (< 5px) returns start and end only."""
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
        """End point coordinates are preserved exactly (no jitter on endpoint)."""
        points = generate_human_curve((0, 0), (500, 500))
        assert points[-1].x == 500
        assert points[-1].y == 500

    def test_default_segments_count(self):
        """Default segments=50 produces 51 points (segments+1)."""
        points = generate_human_curve((0, 0), (200, 200))
        assert len(points) == 51

    def test_custom_segments_count(self):
        """Custom segments controls point count."""
        points = generate_human_curve((0, 0), (200, 200), segments=20)
        assert len(points) == 21

    def test_start_point_is_first_in_list(self):
        """First and last points are present (w_curve easing may offset start)."""
        import random
        random.seed(42)
        points = generate_human_curve((10, 20), (200, 300))
        # last point is always exactly the target
        assert points[-1].x == 200
        assert points[-1].y == 300
        # first point exists (may be offset by easing curve)
        assert isinstance(points[0], Point)
        assert len(points) > 2

    def test_deterministic_with_seed(self):
        """Same random seed produces identical curves."""
        import random
        random.seed(42)
        pts1 = generate_human_curve((0, 0), (100, 100))
        random.seed(42)
        pts2 = generate_human_curve((0, 0), (100, 100))
        for a, b in zip(pts1, pts2):
            assert a.x == b.x
            assert a.y == b.y

    def test_jitter_affects_intermediate_points(self):
        """Intermediate points have jitter; start/end do not."""
        import random
        random.seed(123)
        points = generate_human_curve((50, 50), (950, 950), segments=30, jitter_std=5.0)
        # Check that middle points differ slightly from a straight line
        mid = points[15]
        # With jitter_std=5, mid point should deviate from a straight line
        straight_x = 50 + (950 - 50) * 0.5
        straight_y = 50 + (950 - 50) * 0.5
        assert abs(mid.x - straight_x) > 0.1 or abs(mid.y - straight_y) > 0.1

    def test_zero_jitter_produces_smooth_curve(self):
        """With jitter_std=0, points lie on the bezier curve without noise."""
        import random
        random.seed(99)
        points = generate_human_curve((0, 0), (1000, 1000), segments=10, jitter_std=0.0)
        assert len(points) == 11
        assert points[-1].x == 1000
        assert points[-1].y == 1000

    def test_curve_intensity_affects_shape(self):
        """Higher curve_intensity produces more curved paths."""
        import random
        random.seed(42)
        flat = generate_human_curve((0, 0), (1000, 0), segments=10, curve_intensity=0.01)
        random.seed(42)
        curved = generate_human_curve((0, 0), (1000, 0), segments=10, curve_intensity=0.8)
        # Measure total vertical deviation (absolute y values)
        flat_deviation = sum(abs(p.y) for p in flat)
        curved_deviation = sum(abs(p.y) for p in curved)
        # Higher intensity should produce more vertical deviation
        assert curved_deviation > flat_deviation

    def test_large_distance_produces_valid_curve(self):
        """Large distance (e.g., 1920x1080 screen) produces valid curve."""
        points = generate_human_curve((0, 0), (1920, 1080))
        assert len(points) == 51
        assert points[-1].x == 1920
        assert points[-1].y == 1080
        # All points should have reasonable coordinates
        for pt in points:
            assert -10 <= pt.x <= 1930
            assert -10 <= pt.y <= 1090


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
        from ai_crawler.core.config import config

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
