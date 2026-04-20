"""Tests for TierStrategyMiddleware - LLM-based methods."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from ai_crawler.integrations.middlewares.tier_strategy import TierStrategyMiddleware


class TestTierStrategyInit:
    """TierStrategyMiddleware initialization."""

    def test_init_sets_attributes(self):
        """Middleware initializes with correct attributes."""
        mw = TierStrategyMiddleware()
        assert hasattr(mw, "_profile_generator")
        assert hasattr(mw, "_tier_selector")
        assert hasattr(mw, "_strategy_selector")
        assert hasattr(mw, "_trace_store")

    def test_init_with_llm_api_key(self):
        """Middleware accepts LLM API key."""
        mw = TierStrategyMiddleware(llm_api_key="test-key")
        assert mw._llm_api_key == "test-key"


class TestTierStrategyProfileGenerator:
    """TierStrategyMiddleware._get_profile_generator()"""

    def test_returns_none_without_api_key(self):
        """Returns None when no API key configured."""
        mw = TierStrategyMiddleware()
        result = mw._get_profile_generator()
        assert result is None

    def test_caches_generator(self):
        """Caches the profile generator after first call."""
        mw = TierStrategyMiddleware(llm_api_key="test-key")
        with patch("ai_crawler.core.llm.dspy_model.ProfileGenerator") as MockPG:
            mock_instance = MagicMock()
            MockPG.return_value = mock_instance
            result1 = mw._get_profile_generator()
            result2 = mw._get_profile_generator()
            assert result1 is result2
            assert MockPG.call_count == 1


class TestTierStrategyTierSelector:
    """TierStrategyMiddleware._get_tier_selector()"""

    def test_returns_none_without_api_key(self):
        """Returns None when no API key configured."""
        mw = TierStrategyMiddleware()
        result = mw._get_tier_selector()
        assert result is None


class TestTierStrategyGenerateFingerprint:
    """TierStrategyMiddleware._generate_fingerprint()"""

    def test_returns_default_fingerprint_when_no_llm(self):
        """Returns default fingerprint when LLM not available."""
        mw = TierStrategyMiddleware()
        mock_spider = Mock()
        mock_spider.logger = Mock()
        with patch.object(mw, "_get_profile_generator", return_value=None):
            result = mw._generate_fingerprint(mock_spider)
            assert "user_agent" in result
            assert result["user_agent"] != ""

    def test_uses_generator_when_available(self):
        """Uses profile generator when LLM is available."""
        mw = TierStrategyMiddleware(llm_api_key="test-key")
        mock_spider = Mock()
        mock_spider.logger = Mock()
        mock_generator = MagicMock()
        mock_result = Mock()
        mock_result.user_agent = "Test UA"
        mock_result.sec_ch_ua_platform = "macOS"
        mock_result.sec_ch_ua = '"Not A"'
        mock_result.stealth_args = "[]"
        mock_result.curl_impersonate_target = "chrome120"
        mock_result.timezone_id = "America/New_York"
        mock_result.locale = "en-US"
        mock_result.viewport = {"width": 1920, "height": 1080}
        mock_result.mouse_behavior = "human"
        mock_result.gpu_vendor = "Apple"
        mock_result.gpu_renderer = "M4"
        mock_result.device_pixel_ratio = 2.0
        mock_result.platform_string = "MacIntel"
        mock_result.connection_type = "4g"
        mock_result.downlink = 10
        mock_result.rtt = 50
        mock_result.plugins = []
        mock_result.usb = []
        mock_result.media_devices = []
        mock_result.battery = {}
        mock_result.webdriver_value = ""
        mock_result.permissions_default = "default"
        mock_result.orientation_angle = 0
        mock_result.orientation_type = "landscape-primary"
        mock_generator.return_value = mock_result
        with patch.object(mw, "_get_profile_generator", return_value=mock_generator):
            with patch("ai_crawler.integrations.middlewares.tier_strategy.get_system_facts", return_value="{}"):
                result = mw._generate_fingerprint(mock_spider)
                assert "user_agent" in result


class TestTierStrategyDefaultFingerprint:
    """TierStrategyMiddleware._get_default_fingerprint()"""

    def test_returns_dict(self):
        """Returns a dictionary."""
        mw = TierStrategyMiddleware()
        result = mw._get_default_fingerprint()
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        """Contains all required fingerprint keys."""
        mw = TierStrategyMiddleware()
        result = mw._get_default_fingerprint()
        required_keys = [
            "user_agent",
            "sec_ch_ua_platform",
            "sec_ch_ua",
            "locale",
            "viewport",
        ]
        for key in required_keys:
            assert key in result


class TestTierStrategyInitialTierCache:
    """TierStrategyMiddleware tier caching."""

    def test_cache_key_format(self):
        """Cache key is site:page_type."""
        mw = TierStrategyMiddleware()
        key = mw._initial_tier_cache_key("amazon", "search")
        assert key == "amazon:search"

    def test_cache_invalid_when_empty(self):
        """Cache invalid when empty."""
        mw = TierStrategyMiddleware()
        mw._initial_tier_cache.clear()
        assert mw._is_initial_tier_cache_valid("amazon", "search") is False

    def test_cache_valid_within_ttl(self):
        """Cache valid within TTL."""
        import time

        mw = TierStrategyMiddleware()
        mw._initial_tier_cache.clear()
        mw._initial_tier_cache["amazon:search"] = (3, time.time())
        assert mw._is_initial_tier_cache_valid("amazon", "search") is True


class TestTierStrategySelectInitialTier:
    """TierStrategyMiddleware._select_initial_tier()"""

    def test_returns_fallback_when_no_llm(self):
        """Returns site tier fallback when no LLM."""
        from ai_crawler.core.strategy import PagePattern

        mw = TierStrategyMiddleware()
        mock_spider = Mock()
        mock_spider.logger = Mock()
        with patch.object(mw, "_get_tier_selector", return_value=None):
            tier = mw._select_initial_tier("amazon", PagePattern.SEARCH, mock_spider)
            assert isinstance(tier, int)

    def test_uses_successful_tier_cache(self):
        """Uses cached successful tier when available."""
        import time
        from ai_crawler.core.strategy import PagePattern

        mw = TierStrategyMiddleware()
        mw._initial_tier_cache.clear()
        mw._successful_tier_cache.clear()
        mw._successful_tier_cache["amazon:search"] = (4, time.time())
        mock_spider = Mock()
        mock_spider.logger = Mock()
        tier = mw._select_initial_tier("amazon", PagePattern.SEARCH, mock_spider)
        assert tier == 4


class TestTierStrategySelectStrategyAfterBlock:
    """TierStrategyMiddleware._select_strategy_after_block()"""

    def test_returns_none_when_no_selector(self):
        """Returns None when no strategy selector available."""
        mw = TierStrategyMiddleware()
        mock_spider = Mock()
        mock_spider.logger = Mock()
        task_info = {"site": "amazon", "page_pattern": "search"}
        result = mw._select_strategy_after_block(task_info, "http_403", "", [], mock_spider)
        assert result is None

    def test_returns_strategy_when_selector_available(self):
        """Returns strategy dict when selector returns result."""
        mw = TierStrategyMiddleware(llm_api_key="test-key")
        mock_spider = Mock()
        mock_spider.logger = Mock()
        mock_selector = MagicMock()
        mock_result = Mock()
        mock_result.recommended_strategy = {"proxy": "thordata_dedicated", "render": "playwright"}
        mock_selector.return_value = mock_result
        with patch.object(mw, "_get_strategy_selector", return_value=mock_selector):
            task_info = {"site": "amazon", "page_pattern": "search"}
            result = mw._select_strategy_after_block(
                task_info, "http_403", "Access denied", [], mock_spider
            )
            assert result is not None


class TestTierStrategyDetectBlock:
    """TierStrategyMiddleware._detect_block()"""

    def test_403_returns_blocked(self):
        """HTTP 403 returns blocked."""
        mw = TierStrategyMiddleware()
        mock_response = Mock()
        mock_response.status = 403
        blocked, block_type = mw._detect_block(mock_response)
        assert blocked is True
        assert "403" in block_type

    def test_200_returns_not_blocked(self):
        """HTTP 200 returns not blocked."""
        mw = TierStrategyMiddleware()
        mock_response = Mock()
        mock_response.status = 200
        mock_response.text = "<html><body>Hello</body></html>" * 100
        blocked, block_type = mw._detect_block(mock_response)
        assert blocked is False


class TestTierStrategyIsRenderNeeded:
    """TierStrategyMiddleware._is_render_needed()"""

    def test_true_for_playwright(self):
        """Returns True for PLAYWRIGHT render type."""
        from ai_crawler.core.strategy import CrawlStrategy, RenderType

        mw = TierStrategyMiddleware()
        strategy = CrawlStrategy(render=RenderType.PLAYWRIGHT)
        assert mw._is_render_needed(strategy) is True

    def test_false_for_none(self):
        """Returns False for NONE render type."""
        from ai_crawler.core.strategy import CrawlStrategy, RenderType

        mw = TierStrategyMiddleware()
        strategy = CrawlStrategy(render=RenderType.NONE)
        assert mw._is_render_needed(strategy) is False
