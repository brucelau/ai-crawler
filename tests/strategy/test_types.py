"""Tests for centralized type definitions."""

import pytest

from ai_crawler.core.types import ProxyType, RenderType, TierSystem
from ai_crawler.antidetect.captcha.solver import CaptchaType


class TestProxyType:
    def test_thordata_values(self):
        assert ProxyType.THORDATA_US.value == "thordata_us"
        assert ProxyType.THORDATA_US_CITY.value == "thordata_us_city"
        assert ProxyType.THORDATA_ANY.value == "thordata_any"
        assert ProxyType.THORDATA_DEDICATED.value == "thordata_dedicated"


class TestRenderType:
    def test_render_values(self):
        assert RenderType.NONE.value == "none"
        assert RenderType.PLAYWRIGHT.value == "playwright"
        assert RenderType.CAMOUFOX.value == "camoufox"
        assert RenderType.CLOAKBROWSER.value == "cloakbrowser"
        assert RenderType.CLOUDERA.value == "cloudflare_uc"
        assert RenderType.CLOUDSCRAPER.value == "cloudscraper"
        assert RenderType.SELENIUMBASE.value == "seleniumbase"
        assert RenderType.KAMELEO.value == "kameleo"


class TestTierSystem:
    def test_tier_values(self):
        assert TierSystem.TIER_1.value == 1
        assert TierSystem.TIER_2.value == 2
        assert TierSystem.TIER_3.value == 3
        assert TierSystem.TIER_4.value == 4
        assert TierSystem.TIER_5.value == 5
        assert TierSystem.TIER_6.value == 6
        assert TierSystem.TIER_7.value == 7
        assert TierSystem.TIER_8.value == 8


class TestCaptchaType:
    def test_captcha_values(self):
        assert CaptchaType.RECAPTCHA_V2.value == "recaptcha-v2"
        assert CaptchaType.RECAPTCHA_V3.value == "recaptcha-v3"
        assert CaptchaType.HCAPTCHA.value == "hcaptcha"
        assert CaptchaType.IMAGE_CAPTCHA.value == "imagecaptcha"
        assert CaptchaType.CLOUDFLARE_TURNSTILE.value == "turnstile"
