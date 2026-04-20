"""Tests for WAF detection in TierStrategyMiddleware."""

import pytest
from unittest.mock import Mock
from scrapy.http import HtmlResponse

from ai_crawler.integrations.middlewares.tier_strategy import TierStrategyMiddleware, WAF_SIGNATURES


class TestWafSignatureCoverage:
    """WAF_SIGNATURES should have signatures for all major WAF providers."""

    def test_has_incapsula(self):
        """Incapsula WAF is defined."""
        assert "incapsula" in WAF_SIGNATURES

    def test_incapsula_signatures_include_incap(self):
        """Incapsula has _incap_ signature."""
        assert "_incap_" in WAF_SIGNATURES["incapsula"]

    def test_has_cloudflare(self):
        """Cloudflare WAF is defined."""
        assert "cloudflare" in WAF_SIGNATURES

    def test_cloudflare_signatures_include_cf_ray(self):
        """Cloudflare has cf-ray signature."""
        assert "cf-ray" in WAF_SIGNATURES["cloudflare"]

    def test_has_imperva(self):
        """Imperva WAF is defined."""
        assert "imperva" in WAF_SIGNATURES

    def test_has_akamai(self):
        """Akamai WAF is defined."""
        assert "akamai" in WAF_SIGNATURES

    def test_has_datadome(self):
        """DataDome WAF is defined."""
        assert "datadome" in WAF_SIGNATURES

    def test_datadome_signatures(self):
        """DataDome has datadome_cookie signature."""
        assert "datadome_cookie" in WAF_SIGNATURES["datadome"]

    def test_has_perimeterx(self):
        """PerimeterX WAF is defined."""
        assert "perimeterx" in WAF_SIGNATURES

    def test_has_f5_asm(self):
        """F5 ASM WAF is defined."""
        assert "f5_asm" in WAF_SIGNATURES


class TestDetectWafIncapsula:
    """TierStrategyMiddleware._detect_waf() should detect Incapsula."""

    def test_detects_incap_in_body(self):
        """Incapsula detected from body content."""
        middleware = TierStrategyMiddleware()
        body = b"<html><script>var _incap_12345 = true;</script></html>"
        response = HtmlResponse(url="https://example.com", body=body)
        waf = middleware._detect_waf(response)
        assert waf == "incapsula"

    def test_detects_visid_incap(self):
        """Incapsula detected from visid_incap_ cookie."""
        middleware = TierStrategyMiddleware()
        body = b"<html><body>Incapsula incident</body></html>"
        response = HtmlResponse(
            url="https://example.com",
            headers={"visid_incap_": "abc123"},
            body=body,
        )
        waf = middleware._detect_waf(response)
        assert waf == "incapsula"

    def test_detects_incapsula_incident_id(self):
        """Incapsula detected from incapsula_incident_id."""
        middleware = TierStrategyMiddleware()
        body = b"<html><body>incapsula_incident_id=12345</body></html>"
        response = HtmlResponse(url="https://example.com", body=body)
        waf = middleware._detect_waf(response)
        assert waf == "incapsula"


class TestDetectWafCloudflare:
    """TierStrategyMiddleware._detect_waf() should detect Cloudflare."""

    def test_detects_cf_ray_header(self):
        """Cloudflare detected from cf-ray header."""
        middleware = TierStrategyMiddleware()
        body = b"<html><body>Checking your browser</body></html>"
        response = HtmlResponse(
            url="https://example.com",
            headers={"cf-ray": "abc123xyz"},
            body=body,
        )
        waf = middleware._detect_waf(response)
        assert waf == "cloudflare"

    def test_detects_cf_chl(self):
        """Cloudflare detected from __cf_chl_ in body."""
        middleware = TierStrategyMiddleware()
        body = b"<html><script>var __cf_chl_ = 1;</script></html>"
        response = HtmlResponse(url="https://example.com", body=body)
        waf = middleware._detect_waf(response)
        assert waf == "cloudflare"

    def test_detects_cloudflare_word(self):
        """Cloudflare detected from word in body."""
        middleware = TierStrategyMiddleware()
        body = b"<html><body>Powered by Cloudflare</body></html>"
        response = HtmlResponse(url="https://example.com", body=body)
        waf = middleware._detect_waf(response)
        assert waf == "cloudflare"


class TestDetectWafAkamai:
    """TierStrategyMiddleware._detect_waf() should detect Akamai."""

    def test_detects_akamai_ghost(self):
        """Akamai detected from akamai-ghost header."""
        middleware = TierStrategyMiddleware()
        body = b"<html><body>Akamai</body></html>"
        response = HtmlResponse(
            url="https://example.com",
            headers={"akamai-ghost": "value"},
            body=body,
        )
        waf = middleware._detect_waf(response)
        assert waf == "akamai"

    def test_detects_akamai_x_cache(self):
        """Akamai detected from akamai-x-cache header."""
        middleware = TierStrategyMiddleware()
        body = b"<html><body>Content</body></html>"
        response = HtmlResponse(
            url="https://example.com",
            headers={"akamai-x-cache": "HIT"},
            body=body,
        )
        waf = middleware._detect_waf(response)
        assert waf == "akamai"


class TestDetectWafDataDome:
    """TierStrategyMiddleware._detect_waf() should detect DataDome."""

    def test_detects_datadome_cookie(self):
        """DataDome detected from datadome_cookie header."""
        middleware = TierStrategyMiddleware()
        body = b"<html><body>DataDome protected</body></html>"
        response = HtmlResponse(
            url="https://example.com",
            headers={"datadome_cookie": "xyz"},
            body=body,
        )
        waf = middleware._detect_waf(response)
        assert waf == "datadome"

    def test_detects_datadome_in_body(self):
        """DataDome detected from body content."""
        middleware = TierStrategyMiddleware()
        body = b"<html><script>var _datadome = true;</script></html>"
        response = HtmlResponse(url="https://example.com", body=body)
        waf = middleware._detect_waf(response)
        assert waf == "datadome"


class TestDetectWafPerimeterX:
    """TierStrategyMiddleware._detect_waf() should detect PerimeterX."""

    def test_detects_px_captcha(self):
        """PerimeterX detected from px-captcha."""
        middleware = TierStrategyMiddleware()
        body = b'<html><div class="px-captcha"></div></html>'
        response = HtmlResponse(url="https://example.com", body=body)
        waf = middleware._detect_waf(response)
        assert waf == "perimeterx"

    def test_detects_px3(self):
        """PerimeterX detected from _px3 in body."""
        middleware = TierStrategyMiddleware()
        body = b'<html><script>var _px3 = "abc";</script></html>'
        response = HtmlResponse(url="https://example.com", body=body)
        waf = middleware._detect_waf(response)
        assert waf == "perimeterx"


class TestDetectWafF5ASM:
    """TierStrategyMiddleware._detect_waf() should detect F5 ASM."""

    def test_detects_big_ip(self):
        """F5 ASM detected from BIG-IP."""
        middleware = TierStrategyMiddleware()
        body = b"<html><body>BIG-IP BigIP</body></html>"
        response = HtmlResponse(url="https://example.com", body=body)
        waf = middleware._detect_waf(response)
        assert waf == "f5_asm"


class TestDetectWafCaseInsensitive:
    """WAF detection should be case insensitive."""

    def test_cloudflare_case_insensitive(self):
        """Cloudflare detection is case insensitive."""
        middleware = TierStrategyMiddleware()
        body = b"<html><body>CLOUDFLARE RAY ID</body></html>"
        response = HtmlResponse(url="https://example.com", body=body)
        waf = middleware._detect_waf(response)
        assert waf == "cloudflare"

    def test_incapsula_case_insensitive(self):
        """Incapsula detection is case insensitive."""
        middleware = TierStrategyMiddleware()
        body = b"<html><body>INCAPSULA INCIDENT</body></html>"
        response = HtmlResponse(url="https://example.com", body=body)
        waf = middleware._detect_waf(response)
        assert waf == "incapsula"


class TestDetectWafNoWaf:
    """Normal pages without WAF should return empty string."""

    def test_normal_page_returns_empty(self):
        """Normal page without WAF signatures returns empty string."""
        middleware = TierStrategyMiddleware()
        body = b"<html><body>Welcome to Amazon, here are our products...</body></html>"
        response = HtmlResponse(url="https://example.com", body=body)
        waf = middleware._detect_waf(response)
        assert waf == ""

    def test_non_html_response_returns_empty(self):
        """Non-HTML response returns empty string."""
        middleware = TierStrategyMiddleware()
        response = Mock()
        response.text = None
        waf = middleware._detect_waf(response)
        assert waf == ""


class TestDetectWafHeaderAndBody:
    """WAF can be detected from headers or body."""

    def test_header_takes_priority(self):
        """WAF detected from header even if body is normal."""
        middleware = TierStrategyMiddleware()
        body = b"<html><body>Normal page</body></html>"
        response = HtmlResponse(
            url="https://example.com",
            headers={"cf-ray": "abc123", "visid_incap_": "xyz"},
            body=body,
        )
        waf = middleware._detect_waf(response)
        assert waf in ["cloudflare", "incapsula"]
