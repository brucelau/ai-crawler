"""Tests for CaptchaDetector - unified captcha detection logic."""

import pytest

from ai_crawler.integrations.captcha.detector import CaptchaDetector


class TestCaptchaDetectorInit:
    def test_init_with_api_key(self):
        detector = CaptchaDetector(api_key="test-key")
        assert detector._api_key == "test-key"

    def test_init_without_api_key(self):
        detector = CaptchaDetector()
        assert detector._api_key is None


class TestCaptchaDetection:
    def test_detects_recaptcha_v2(self):
        detector = CaptchaDetector()
        html = '<div class="g-recaptcha" data-sitekey="TEST_KEY"></div>'
        detected, captcha_type, site_key, action = detector.detect(html)
        assert detected is True
        assert captcha_type == "recaptcha-v2"

    def test_detects_recaptcha_v3(self):
        detector = CaptchaDetector()
        html = "https://www.google.com/recaptcha/api.js?render=V3_KEY"
        detected, captcha_type, site_key, action = detector.detect(html)
        assert detected is True
        assert captcha_type == "recaptcha-v3"

    def test_detects_hcaptcha(self):
        detector = CaptchaDetector()
        html = '<div class="h-captcha" data-sitekey="HCAPTCHA_KEY"></div>'
        detected, captcha_type, site_key, action = detector.detect(html)
        assert detected is True
        assert captcha_type == "hcaptcha"

    def test_detects_image_captcha(self):
        detector = CaptchaDetector()
        html = '<input type="image" src="/captcha.png" />'
        detected, captcha_type, site_key, action = detector.detect(html)
        assert detected is True
        assert captcha_type == "imagecaptcha"

    def test_detects_cloudflare_turnstile(self):
        detector = CaptchaDetector()
        html = "cf-challengeturnstile"
        detected, captcha_type, site_key, action = detector.detect(html)
        assert detected is True

    def test_no_captcha(self):
        detector = CaptchaDetector()
        html = "<html><body>Normal page</body></html>"
        detected, captcha_type, site_key, action = detector.detect(html)
        assert detected is False

    def test_non_200_status_returns_false(self):
        detector = CaptchaDetector()
        html = '<div class="g-recaptcha" data-sitekey="TEST_KEY"></div>'
        detected, captcha_type, site_key, action = detector.detect(html, status_code=403)
        assert detected is False


class TestCaptchaSolverIntegration:
    def test_solve_raises_without_solver(self):
        detector = CaptchaDetector()
        with pytest.raises(ValueError, match="No captcha solver configured"):
            detector.solve("recaptcha-v2", "KEY", "http://example.com", None)
