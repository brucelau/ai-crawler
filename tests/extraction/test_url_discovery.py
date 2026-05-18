"""Tests for URLDiscovery - LLM-based URL format discovery."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from ai_crawler.llm.url_discovery import URLDiscovery


class TestURLDiscoveryInit:
    """URLDiscovery initialization."""

    def test_singleton_pattern(self):
        """URLDiscovery uses singleton pattern."""
        d1 = URLDiscovery()
        d2 = URLDiscovery()
        assert d1 is d2


class TestURLDiscoveryCacheValidity:
    """URLDiscovery._is_cache_valid() should check cache TTL."""

    def test_cache_invalid_when_empty(self):
        """Cache is invalid when site not in cache."""
        discovery = URLDiscovery()
        discovery._cache.clear()
        assert discovery._is_cache_valid("amazon") is False

    def test_cache_valid_within_ttl(self):
        """Cache is valid when within TTL."""
        import time

        discovery = URLDiscovery()
        discovery._cache.clear()
        discovery._cache["amazon"] = {"_cached_at": time.time()}
        assert discovery._is_cache_valid("amazon") is True

    def test_cache_invalid_after_ttl(self):
        """Cache is invalid after TTL expires."""
        import time

        discovery = URLDiscovery()
        discovery._cache.clear()
        old_time = time.time() - discovery._cache_ttl - 1
        discovery._cache["amazon"] = {"_cached_at": old_time}
        assert discovery._is_cache_valid("amazon") is False


class TestURLDiscoveryDefaultUrlFormat:
    """URLDiscovery._default_url_format() should return fallback patterns."""

    def test_amazon_defaults(self):
        """Amazon has predefined URL patterns."""
        result = URLDiscovery()._default_url_format("amazon")
        assert result["site"] == "amazon"
        assert "amazon.com" in result["search_url_pattern"]
        assert "{query}" in result["search_url_pattern"]

    def test_walmart_defaults(self):
        """Walmart has predefined URL patterns."""
        result = URLDiscovery()._default_url_format("walmart")
        assert result["site"] == "walmart"
        assert result["search_param"] == "q"

    def test_target_defaults(self):
        """Target has predefined URL patterns."""
        result = URLDiscovery()._default_url_format("target")
        assert result["site"] == "target"
        assert "target.com" in result["search_url_pattern"]

    def test_unknown_site_generates_pattern(self):
        """Unknown site generates pattern from site name."""
        result = URLDiscovery()._default_url_format("unknownsite")
        assert result["site"] == "unknownsite"
        assert "unknownsite.com" in result["search_url_pattern"]


class TestURLDiscoveryDiscoverUrlFormat:
    """URLDiscovery._discover_url_format() should use LLM when available."""

    def test_returns_defaults_when_no_llm(self):
        """Returns default format when LLM not available."""
        discovery = URLDiscovery()
        with patch.object(discovery, "_get_dspy_discoverer", return_value=None):
            result = discovery._discover_url_format("amazon", "<html></html>")
            assert result["site"] == "amazon"

    def test_uses_dspy_when_available(self):
        """Uses DSPy discoverer when configured."""
        discovery = URLDiscovery()
        mock_result = Mock()
        mock_result.__dict__ = {
            "site": "amazon",
            "search_url_pattern": "https://amazon.com/s?k={query}",
        }
        with patch.object(discovery, "_get_dspy_discoverer", return_value=mock_result):
            with patch(
                "ai_crawler.llm.url_discovery.validate_url_discovery"
            ) as mock_validate:
                mock_validate.return_value = Mock(model_dump=lambda: {"site": "amazon"})
                result = discovery._discover_url_format("amazon", "<html>test</html>")
                assert "site" in result


class TestURLDiscoveryGetUrlFormat:
    """URLDiscovery.get_url_format() should return cached or fresh format."""

    def test_returns_cached_when_valid(self):
        """Returns cached format when cache is valid."""
        import time

        discovery = URLDiscovery()
        discovery._cache.clear()
        discovery._cache["amazon"] = {
            "_cached_at": time.time(),
            "site": "amazon",
            "search_url_pattern": "https://amazon.com/s?k={query}",
        }
        result = discovery.get_url_format("amazon")
        assert "amazon.com" in result["search_url_pattern"]

    def test_discovers_when_cache_invalid(self):
        """Discovers new format when cache is invalid."""
        discovery = URLDiscovery()
        discovery._cache.clear()
        with patch.object(
            discovery,
            "_discover_url_format",
            return_value={
                "site": "amazon",
                "search_url_pattern": "https://amazon.com/new",
                "_cached_at": 0,
            },
        ):
            result = discovery.get_url_format("amazon", "<html></html>")
            assert result["search_url_pattern"] == "https://amazon.com/new"


class TestURLDiscoveryBuildSearchUrl:
    """URLDiscovery.build_search_url() should construct search URLs."""

    def test_builds_simple_search_url(self):
        """Builds URL with query parameter."""
        discovery = URLDiscovery()
        discovery._cache["amazon"] = {
            "_cached_at": 0,
            "site": "amazon",
            "search_url_pattern": "https://amazon.com/s?k={query}",
            "search_param": "k",
            "page_param": "page",
        }
        url = discovery.build_search_url("amazon", "test")
        assert "amazon.com" in url
        assert "k=test" in url

    def test_builds_url_with_page(self):
        """Builds URL with page parameter."""
        discovery = URLDiscovery()
        discovery._cache["amazon"] = {
            "_cached_at": 0,
            "site": "amazon",
            "search_url_pattern": "https://amazon.com/s?k={query}",
            "search_param": "k",
            "page_param": "page",
        }
        url = discovery.build_search_url("amazon", "test", page=2)
        assert "page=2" in url

    def test_page_param_not_added_on_first_page(self):
        """Page parameter not added when page=1."""
        discovery = URLDiscovery()
        discovery._cache["amazon"] = {
            "_cached_at": 0,
            "site": "amazon",
            "search_url_pattern": "https://amazon.com/s?k={query}",
            "search_param": "k",
            "page_param": "page",
        }
        url = discovery.build_search_url("amazon", "test", page=1)
        assert "page=" not in url

    def test_builds_url_without_placeholder(self):
        """Builds URL when pattern has no placeholder - appends query param."""
        import time

        discovery = URLDiscovery()
        discovery._cache["amazon"] = {
            "_cached_at": time.time(),
            "site": "amazon",
            "search_url_pattern": "https://www.example.com/search",
            "search_param": "q",
            "page_param": "page",
        }
        url = discovery.build_search_url("amazon", "test")
        assert "example.com/search" in url
        assert "q=test" in url


class TestURLDiscoveryInvalidateCache:
    """URLDiscovery.invalidate_cache() should clear cache."""

    def test_invalidate_single_site(self):
        """Invalidates cache for specific site."""
        import time

        discovery = URLDiscovery()
        discovery._cache["amazon"] = {"_cached_at": time.time()}
        discovery._cache["walmart"] = {"_cached_at": time.time()}
        discovery.invalidate_cache("amazon")
        assert "amazon" not in discovery._cache
        assert "walmart" in discovery._cache

    def test_invalidate_all_sites(self):
        """Invalidates cache for all sites."""
        import time

        discovery = URLDiscovery()
        discovery._cache["amazon"] = {"_cached_at": time.time()}
        discovery._cache["walmart"] = {"_cached_at": time.time()}
        discovery.invalidate_cache()
        assert len(discovery._cache) == 0


class TestDiscoverSiteUrlFunction:
    """discover_site_url() module function."""

    def test_discover_site_url_exists(self):
        """Module function exists."""
        from ai_crawler.llm.url_discovery import discover_site_url

        assert callable(discover_site_url)

    def test_discover_site_url_returns_string(self):
        """Returns string URL."""
        from ai_crawler.llm.url_discovery import discover_site_url

        result = discover_site_url("amazon", "test query")
        assert isinstance(result, str)
        assert "amazon.com" in result
