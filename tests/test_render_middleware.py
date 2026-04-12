"""Tests for TierStrategyMiddleware and RenderMiddleware."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from scrapy import Spider, Request
from scrapy.http import HtmlResponse

from ai_crawler.middlewares.tier_strategy import (
    TierStrategyMiddleware,
    RenderMiddleware,
    WAF_SIGNATURES,
)
from ai_crawler.core.strategy import CrawlStrategy, CrawlTask, ProxyType, RenderType, PagePattern


class TestWafSignatures:
    """WAF_SIGNATURES should contain detection patterns for major WAF providers."""

    def test_waf_signatures_defined(self):
        """All expected WAF types have signatures."""
        assert "incapsula" in WAF_SIGNATURES
        assert "cloudflare" in WAF_SIGNATURES
        assert "akamai" in WAF_SIGNATURES
        assert "datadome" in WAF_SIGNATURES
        assert "perimeterx" in WAF_SIGNATURES

    def test_cloudflare_has_ray_id(self):
        """Cloudflare signatures include cf-ray."""
        assert "cf-ray" in WAF_SIGNATURES["cloudflare"]

    def test_incapsula_signatures(self):
        """Incapsula signatures include _incap_."""
        assert "_incap_" in WAF_SIGNATURES["incapsula"]


class TestTierStrategyMiddlewareInit:
    """TierStrategyMiddleware.__init__ should initialize all components."""

    def test_init_without_llm(self):
        """Middleware initializes with defaults when no LLM key."""
        middleware = TierStrategyMiddleware()
        assert middleware._llm_api_key is None
        assert middleware._profile_generator is None
        assert middleware._tier_selector is None
        assert middleware._trace_store is not None

    def test_init_with_llm_key(self):
        """Middleware stores LLM API key when provided."""
        middleware = TierStrategyMiddleware(llm_api_key="test-key")
        assert middleware._llm_api_key == "test-key"

    def test_init_creates_detector(self):
        """Middleware creates BlockDetector instance."""
        middleware = TierStrategyMiddleware()
        assert middleware.detector is not None

    def test_from_crawler_extracts_settings(self):
        """from_crawler extracts LLM_API_KEY and TRACE_DIR from settings."""
        crawler = Mock()
        crawler.settings.get.side_effect = lambda key, default=None: {
            "LLM_API_KEY": "my-key",
            "TRACE_DIR": "my-traces",
        }.get(key, default)

        middleware = TierStrategyMiddleware.from_crawler(crawler)
        assert middleware._llm_api_key == "my-key"


class TestTierStrategyMiddlewareDetectWaf:
    """TierStrategyMiddleware._detect_waf() should identify WAF providers."""

    def test_detects_cloudflare(self):
        """HTML with cf-ray header detects Cloudflare."""
        middleware = TierStrategyMiddleware()
        response = HtmlResponse(
            url="https://example.com",
            headers={"cf-ray": "abc123"},
            body=b"<html>Checking your browser</html>",
        )
        waf = middleware._detect_waf(response)
        assert waf == "cloudflare"

    def test_detects_incapsula(self):
        """HTML with _incap_ detects Incapsula."""
        middleware = TierStrategyMiddleware()
        body = b"<html><script>_incap_12345</script></html>"
        response = HtmlResponse(url="https://example.com", body=body)
        waf = middleware._detect_waf(response)
        assert waf == "incapsula"

    def test_detects_datadome(self):
        """HTML with datadome_cookie detects DataDome."""
        middleware = TierStrategyMiddleware()
        body = b"<html><script>datadome_cookie='xyz'</script></html>"
        response = HtmlResponse(url="https://example.com", body=body)
        waf = middleware._detect_waf(response)
        assert waf == "datadome"

    def test_no_waf_returns_empty_string(self):
        """Normal HTML without WAF signatures returns empty string."""
        middleware = TierStrategyMiddleware()
        body = b"<html><body>Normal product page</body></html>"
        response = HtmlResponse(url="https://example.com", body=body)
        waf = middleware._detect_waf(response)
        assert waf == ""


class TestTierStrategyMiddlewareIsRenderNeeded:
    """TierStrategyMiddleware._is_render_needed() should return True for render types."""

    def test_needs_render_for_camoufox(self):
        """CAMOUFOX requires rendering."""
        middleware = TierStrategyMiddleware()
        strategy = CrawlStrategy(render=RenderType.CAMOUFOX)
        assert middleware._is_render_needed(strategy) is True

    def test_needs_render_for_cloakbrowser(self):
        """CLOAKBROWSER requires rendering."""
        middleware = TierStrategyMiddleware()
        strategy = CrawlStrategy(render=RenderType.CLOAKBROWSER)
        assert middleware._is_render_needed(strategy) is True

    def test_needs_render_for_playwright(self):
        """PLAYWRIGHT requires rendering."""
        middleware = TierStrategyMiddleware()
        strategy = CrawlStrategy(render=RenderType.PLAYWRIGHT)
        assert middleware._is_render_needed(strategy) is True

    def test_needs_render_for_seleniumbase(self):
        """SELENIUMBASE requires rendering."""
        middleware = TierStrategyMiddleware()
        strategy = CrawlStrategy(render=RenderType.SELENIUMBASE)
        assert middleware._is_render_needed(strategy) is True

    def test_needs_render_for_cloudflare_uc(self):
        """CLOUDERA requires rendering."""
        middleware = TierStrategyMiddleware()
        strategy = CrawlStrategy(render=RenderType.CLOUDERA)
        assert middleware._is_render_needed(strategy) is True

    def test_needs_render_for_kameleo(self):
        """KAMELEO requires rendering."""
        middleware = TierStrategyMiddleware()
        strategy = CrawlStrategy(render=RenderType.KAMELEO)
        assert middleware._is_render_needed(strategy) is True

    def test_needs_render_for_cloudscraper(self):
        """CLOUDSCRAPER requires rendering."""
        middleware = TierStrategyMiddleware()
        strategy = CrawlStrategy(render=RenderType.CLOUDSCRAPER)
        assert middleware._is_render_needed(strategy) is True

    def test_no_render_for_none(self):
        """NONE render type does not require rendering."""
        middleware = TierStrategyMiddleware()
        strategy = CrawlStrategy(render=RenderType.NONE)
        assert middleware._is_render_needed(strategy) is False


class TestTierStrategyMiddlewareCreateTask:
    """TierStrategyMiddleware._create_task() should build CrawlTask from request."""

    def test_creates_task_with_url_and_site(self):
        """Task is created with correct URL and site from request meta."""
        middleware = TierStrategyMiddleware()
        request = Request(
            url="https://www.amazon.com/s?k=test",
            meta={"site": "amazon"},
        )
        task = middleware._create_task(request)
        assert task.url == "https://www.amazon.com/s?k=test"
        assert task.site == "amazon"

    def test_detects_site_from_url(self):
        """Site is extracted from URL when not in meta."""
        middleware = TierStrategyMiddleware()
        request = Request(url="https://www.walmart.com/search?q=test")
        task = middleware._create_task(request)
        assert task.site == "walmart"

    def test_detects_page_pattern(self):
        """Task includes detected page pattern."""
        middleware = TierStrategyMiddleware()
        request = Request(
            url="https://www.amazon.com/dp/B08N5WRWNW",
            meta={"site": "amazon"},
        )
        task = middleware._create_task(request)
        assert task.page_pattern == PagePattern.DETAIL


class TestTierStrategyMiddlewareGetStartTier:
    """TierStrategyMiddleware._get_start_tier() should determine initial tier."""

    def test_uses_site_tier_default(self):
        """Start tier is determined by site and pattern defaults."""
        middleware = TierStrategyMiddleware()
        request = Request(
            url="https://www.amazon.com/s?k=test",
            meta={"site": "amazon"},
        )
        tier = middleware._get_start_tier(request, None)
        assert tier == 6

    def test_extracts_site_from_url(self):
        """Site is extracted from URL if not in meta."""
        middleware = TierStrategyMiddleware()
        request = Request(url="https://www.target.com/s?searchTerm=test")
        tier = middleware._get_start_tier(request, None)
        assert tier == 6


class TestTierStrategyMiddlewareGetStrategies:
    """TierStrategyMiddleware._get_strategies() should return tier strategies."""

    def test_returns_tier_1_to_8_by_default(self):
        """get_strategies returns all tiers 1-8."""
        middleware = TierStrategyMiddleware()
        strategies = middleware._get_strategies(1)
        assert len(strategies) == 8
        assert strategies[0].tier == 1
        assert strategies[-1].tier == 8

    def test_returns_starting_from_given_tier(self):
        """get_strategies starts from the given tier."""
        middleware = TierStrategyMiddleware()
        strategies = middleware._get_strategies(5)
        assert len(strategies) == 4
        assert strategies[0].tier == 5


class TestTierStrategyMiddlewareDetectBlock:
    """TierStrategyMiddleware._detect_block() should identify blocking."""

    def test_403_is_blocked(self):
        """HTTP 403 is detected as blocked."""
        middleware = TierStrategyMiddleware()
        response = HtmlResponse(url="https://example.com", status=403, body=b"403")
        blocked, block_type = middleware._detect_block(response)
        assert blocked is True
        assert block_type == "http_403"

    def test_429_is_blocked(self):
        """HTTP 429 is detected as blocked."""
        middleware = TierStrategyMiddleware()
        response = HtmlResponse(url="https://example.com", status=429, body=b"429")
        blocked, block_type = middleware._detect_block(response)
        assert blocked is True
        assert block_type == "http_429"

    def test_200_normal_page_not_blocked(self):
        """Normal 200 response is not blocked."""
        middleware = TierStrategyMiddleware()
        body = b"<html>" + b"x" * 5000 + b"</html>"
        response = HtmlResponse(url="https://example.com", status=200, body=body)
        blocked, block_type = middleware._detect_block(response)
        assert blocked is False


class TestRenderMiddlewareIsRenderNeeded:
    """RenderMiddleware should correctly identify which render types need JS rendering."""

    def test_all_browser_renders_need_js(self):
        """All browser-based render types should need JS rendering."""
        browser_renders = [
            RenderType.PLAYWRIGHT,
            RenderType.CAMOUFOX,
            RenderType.CLOAKBROWSER,
            RenderType.SELENIUMBASE,
            RenderType.CLOUDERA,
            RenderType.KAMELEO,
        ]
        for render_type in browser_renders:
            strategy = CrawlStrategy(render=render_type)
            middleware = TierStrategyMiddleware()
            assert middleware._is_render_needed(strategy) is True, (
                f"{render_type} should need JS rendering"
            )
