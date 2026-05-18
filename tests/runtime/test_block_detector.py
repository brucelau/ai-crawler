"""Tests for BlockDetector - anti-bot detection logic."""

import pytest
from ai_crawler.antidetect.handler import BlockDetectionContext, BlockDetector, BlockType


class TestBlockDetector:
    """BlockDetector.detect() should identify various blocking scenarios."""

    def test_http_403_returns_blocked(self):
        """HTTP 403 Forbidden → blocked, type HTTP_403."""
        detector = BlockDetector()
        text = "<html><body>403 Forbidden</body></html>" * 100
        blocked, block_type = detector.detect(403, text, len(text))
        assert blocked is True
        assert block_type == BlockType.HTTP_403

    def test_http_429_returns_blocked(self):
        """HTTP 429 Too Many Requests → blocked, type HTTP_429."""
        detector = BlockDetector()
        text = "<html><body>429 Rate Limited</body></html>" * 100
        blocked, block_type = detector.detect(429, text, len(text))
        assert blocked is True
        assert block_type == BlockType.HTTP_429

    def test_http_451_returns_blocked(self):
        """HTTP 451 Unavailable For Legal Reasons → blocked, type HTTP_451."""
        detector = BlockDetector()
        text = "<html><body>451 Unavailable</body></html>" * 100
        blocked, block_type = detector.detect(451, text, len(text))
        assert blocked is True
        assert block_type == BlockType.HTTP_451

    def test_http_500_returns_blocked(self):
        """HTTP 500+ server error → blocked, type HTTP_TIMEOUT."""
        detector = BlockDetector()
        text = "<html><body>Internal Server Error</body></html>" * 100
        blocked, block_type = detector.detect(500, text, len(text))
        assert blocked is True
        assert block_type == BlockType.HTTP_TIMEOUT

    def test_none_status_returns_blocked(self):
        """None status (timeout/connection error) → blocked, type HTTP_TIMEOUT."""
        detector = BlockDetector()
        text = ""
        blocked, block_type = detector.detect(None, text, 0)
        assert blocked is True
        assert block_type == BlockType.HTTP_TIMEOUT

    def test_empty_response_returns_blocked(self):
        """Short response (< 1000 chars, content < 5000) → blocked, type EMPTY_RESPONSE."""
        detector = BlockDetector()
        short_text = "<html></html>"  # very short, < 1000 chars and < 5000 bytes
        blocked, block_type = detector.detect(200, short_text, len(short_text))
        assert blocked is True
        assert block_type == BlockType.EMPTY_RESPONSE

    def test_captcha_phrase_detected(self):
        """Page containing 'prove you're not a robot' → blocked, type CAPTCHA."""
        detector = BlockDetector()
        text = "Please prove you're not a robot to continue" * 50
        blocked, block_type = detector.detect(200, text, len(text))
        assert blocked is True
        assert block_type == BlockType.CAPTCHA

    def test_are_you_a_robot_detected(self):
        """Page containing 'are you a robot' → blocked, type CAPTCHA."""
        detector = BlockDetector()
        text = "Are you a robot? Please verify you're human" * 50
        blocked, block_type = detector.detect(200, text, len(text))
        assert blocked is True
        assert block_type == BlockType.CAPTCHA

    def test_recaptcha_detected(self):
        """Page containing 'recaptcha' → blocked, type CAPTCHA."""
        detector = BlockDetector()
        text = "Please complete the recaptcha verification" * 50
        blocked, block_type = detector.detect(200, text, len(text))
        assert blocked is True
        assert block_type == BlockType.CAPTCHA

    def test_cloudflare_keyword_detected(self):
        """Page containing 'cloudflare' → blocked, type CLOUDFLARE."""
        detector = BlockDetector()
        text = "Cloudflare is checking your browser" * 50
        blocked, block_type = detector.detect(200, text, len(text))
        assert blocked is True
        assert block_type == BlockType.CLOUDFLARE

    def test_cf_challenge_keyword_detected(self):
        """Page containing 'cf-challenge' → blocked, type CLOUDFLARE."""
        detector = BlockDetector()
        text = "cf-challenge / ray ID" * 100
        blocked, block_type = detector.detect(200, text, len(text))
        assert blocked is True
        assert block_type == BlockType.CLOUDFLARE

    def test_checking_your_browser_keyword_detected(self):
        """Page containing 'checking your browser' → blocked, type CLOUDFLARE."""
        detector = BlockDetector()
        text = "Checking your browser before accessing" * 50
        blocked, block_type = detector.detect(200, text, len(text))
        assert blocked is True
        assert block_type == BlockType.CLOUDFLARE

    def test_prove_not_robot_detected(self):
        """Page containing 'prove you're not a robot' → blocked, type CAPTCHA."""
        detector = BlockDetector()
        text = "Please prove you're not a robot to continue browsing" * 50
        blocked, block_type = detector.detect(200, text, len(text))
        assert blocked is True
        assert block_type == BlockType.CAPTCHA

    def test_automated_requests_detected(self):
        """Page containing 'automated requests' → blocked, type BOT_DETECTED."""
        detector = BlockDetector()
        text = "Automated requests are not allowed" * 50
        blocked, block_type = detector.detect(200, text, len(text))
        assert blocked is True
        assert block_type == BlockType.BOT_DETECTED

    def test_access_denied_keyword_detected(self):
        """Page containing 'access denied' → blocked, type BOT_DETECTED."""
        detector = BlockDetector()
        text = "Access denied. Please contact administrator" * 50
        blocked, block_type = detector.detect(200, text, len(text))
        assert blocked is True
        assert block_type == BlockType.BOT_DETECTED

    def test_blocked_ip_detected(self):
        """Page containing 'blocked your ip' → blocked, type BOT_DETECTED."""
        detector = BlockDetector()
        text = (
            "Your request was blocked your ip address has been blocked please contact support" * 50
        )
        blocked, block_type = detector.detect(200, text, len(text))
        assert blocked is True
        assert block_type == BlockType.BOT_DETECTED

    def test_normal_page_returns_not_blocked(self):
        """Normal long page → not blocked."""
        detector = BlockDetector()
        # Build a realistic page > 1000 chars and > 5000 bytes
        text = "<html><body>" + ("Product name, price, description. " * 200) + "</body></html>"
        blocked, block_type = detector.detect(200, text, len(text))
        assert blocked is False
        assert block_type == BlockType.NONE

    def test_200_with_long_content_not_blocked(self):
        """HTTP 200 with substantial content → not blocked."""
        detector = BlockDetector()
        text = (
            """
        <!DOCTYPE html>
        <html>
        <head><title>Product Listing</title></head>
        <body>
        <div class="product">Inflatable Costume - $29.99</div>
        <div class="product">Party Decoration - $14.99</div>
        """
            * 200
        )
        blocked, block_type = detector.detect(200, text, len(text))
        assert blocked is False
        assert block_type == BlockType.NONE

    def test_priority_403_over_content_keywords(self):
        """HTTP 403 should return HTTP_403 even if content looks normal."""
        detector = BlockDetector()
        text = "Normal product listing page content " * 100
        blocked, block_type = detector.detect(403, text, len(text))
        assert blocked is True
        assert block_type == BlockType.HTTP_403

    def test_priority_429_over_captcha_content(self):
        """HTTP 429 should return HTTP_429 even if content mentions captcha."""
        detector = BlockDetector()
        text = "captcha challenge page content " * 100
        blocked, block_type = detector.detect(429, text, len(text))
        assert blocked is True
        assert block_type == BlockType.HTTP_429

    def test_empty_response_short_text(self):
        """Short text + small content_length → EMPTY_RESPONSE."""
        detector = BlockDetector()
        text = "x" * 500
        blocked, block_type = detector.detect(200, text, 500)
        assert blocked is True
        assert block_type == BlockType.EMPTY_RESPONSE

    def test_empty_response_content_length_below_threshold(self):
        """Long text but content_length < 5000 → EMPTY_RESPONSE (OR condition)."""
        detector = BlockDetector()
        text = "x" * 2000
        blocked, block_type = detector.detect(200, text, 4999)
        assert blocked is True
        assert block_type == BlockType.EMPTY_RESPONSE

    def test_short_valid_product_page_not_blocked(self):
        """Thin but valid ecommerce detail page should not be marked EMPTY_RESPONSE."""
        detector = BlockDetector()
        text = """
        <html><body>
        <div class="product-title">Premium Patio Chair</div>
        <button>Add to Cart</button>
        <script type="application/ld+json">{"@type":"Product","name":"Premium Patio Chair"}</script>
        </body></html>
        """
        blocked, block_type = detector.detect(200, text, len(text))
        assert blocked is False
        assert block_type == BlockType.NONE

    def test_valid_page_with_recaptcha_script_reference_not_blocked(self):
        """Weak captcha terms inside a valid product page should not trigger a block."""
        detector = BlockDetector()
        text = """
        <html><body>
        <div data-asin="B001234">Inflatable Costume</div>
        <div class="price-current">$29.99</div>
        <script src="https://www.google.com/recaptcha/api.js"></script>
        </body></html>
        """
        blocked, block_type = detector.detect(200, text, len(text))
        assert blocked is False
        assert block_type == BlockType.NONE

    def test_valid_page_with_cloudflare_reference_not_blocked(self):
        """Cloudflare string alone should not block a healthy result page with success signals."""
        detector = BlockDetector()
        text = """
        <html><body>
        <div class="product-card">Pool Float</div>
        <div class="product-tile">Summer Pool Float</div>
        <footer>Protected by Cloudflare CDN</footer>
        </body></html>
        """
        blocked, block_type = detector.detect(200, text, len(text))
        assert blocked is False
        assert block_type == BlockType.NONE

    def test_short_search_results_page_with_multiple_product_signals_not_blocked(self):
        """Thin search pages with repeated product signals should not be marked blocked."""
        detector = BlockDetector()
        text = """
        <html><body>
        <div class="product-card">Chair One</div>
        <div class="product-tile">Chair Two</div>
        <div class="price-current">$19.99</div>
        <div>Results for chair</div>
        </body></html>
        """
        blocked, block_type = detector.detect(200, text, len(text))
        assert blocked is False
        assert block_type == BlockType.NONE

    def test_review_page_pattern_allows_review_page_signals(self):
        detector = BlockDetector()
        text = """
        <html><body>
        <div>Customer Reviews</div>
        <div>4.7 out of 5 stars</div>
        <div>Verified Purchase</div>
        <div>Write a review</div>
        </body></html>
        """
        context = BlockDetectionContext(page_pattern="review")
        blocked, block_type = detector.detect(200, text, len(text), context)
        assert blocked is False
        assert block_type == BlockType.NONE

    def test_detail_page_pattern_uses_goal_fallback_when_pattern_unknown(self):
        detector = BlockDetector()
        text = """
        <html><body>
        <div>Premium Patio Chair</div>
        <button>Add to Cart</button>
        <div>Product Details</div>
        </body></html>
        """
        context = BlockDetectionContext(page_pattern="unknown", goal="detail")
        blocked, block_type = detector.detect(200, text, len(text), context)
        assert blocked is False
        assert block_type == BlockType.NONE

    def test_search_page_pattern_is_more_tolerant_of_short_result_structures(self):
        detector = BlockDetector()
        text = """
        <html><body>
        <div>Results for chairs</div>
        <div class="product-grid"></div>
        </body></html>
        """
        context = BlockDetectionContext(page_pattern="search")
        blocked, block_type = detector.detect(200, text, len(text), context)
        assert blocked is False
        assert block_type == BlockType.NONE

    def test_weak_verify_phrase_does_not_block_detail_page_with_success_signals(self):
        detector = BlockDetector()
        text = """
        <html><body>
        <div class="product-title">Inflatable Costume</div>
        <button>Add to Cart</button>
        <footer>Please verify fit before purchase</footer>
        </body></html>
        """
        context = BlockDetectionContext(page_pattern="detail")
        blocked, block_type = detector.detect(200, text, len(text), context)
        assert blocked is False
        assert block_type == BlockType.NONE

    def test_weak_cloudflare_signal_is_overridden_by_semantic_confirmation(self):
        detector = BlockDetector()
        text = "<html><body>cloudflare cdn edge cache</body></html>"
        context = BlockDetectionContext(
            page_pattern="search",
            semantic_confirmation={"kind": "search", "confidence": 0.9, "entity_count": 3},
        )
        blocked, block_type = detector.detect(200, text, len(text), context)
        assert blocked is False
        assert block_type == BlockType.NONE

    def test_empty_response_is_overridden_by_semantic_confirmation(self):
        detector = BlockDetector()
        text = "<html><body>x</body></html>"
        context = BlockDetectionContext(
            page_pattern="detail",
            semantic_confirmation={
                "kind": "detail",
                "confidence": 0.7,
                "entity_count": 1,
                "has_price": True,
            },
        )
        blocked, block_type = detector.detect(200, text, len(text), context)
        assert blocked is False
        assert block_type == BlockType.NONE

    def test_strong_captcha_signal_is_not_overridden_by_semantic_confirmation(self):
        detector = BlockDetector()
        text = "Please prove you're not a robot to continue"
        context = BlockDetectionContext(
            page_pattern="detail",
            semantic_confirmation={
                "kind": "detail",
                "confidence": 0.95,
                "entity_count": 1,
                "has_price": True,
            },
        )
        blocked, block_type = detector.detect(200, text, len(text), context)
        assert blocked is True
        assert block_type == BlockType.CAPTCHA

    def test_browser_error_page_is_treated_as_timeout_block(self):
        detector = BlockDetector()
        text = """
        <html><head><title>www.amazon.com</title></head>
        <body>This site can't be reached. ERR_NO_SUPPORTED_PROXIES</body></html>
        """
        context = BlockDetectionContext(page_pattern="search")
        blocked, block_type = detector.detect(200, text, len(text), context)
        assert blocked is True
        assert block_type == BlockType.HTTP_TIMEOUT

    def test_localized_browser_error_page_is_treated_as_timeout_block(self):
        detector = BlockDetector()
        text = """
        <html><body>无法访问此网站 网页可能暂时无法连接，或者它已永久性地移动到了新网址。 ERR_NO_SUPPORTED_PROXIES</body></html>
        """
        blocked, block_type = detector.detect(
            200, text, len(text), BlockDetectionContext(page_pattern="search")
        )
        assert blocked is True
        assert block_type == BlockType.HTTP_TIMEOUT

    def test_amazon_sorry_page_is_treated_as_timeout_block(self):
        detector = BlockDetector()
        text = """
        <html><head><title>Sorry! Something went wrong!</title></head>
        <body>Sorry! Something went wrong! We couldn't process your request.</body></html>
        """
        blocked, block_type = detector.detect(
            200, text, len(text), BlockDetectionContext(page_pattern="search")
        )
        assert blocked is True
        assert block_type == BlockType.HTTP_TIMEOUT

    def test_missing_runtime_module_page_is_treated_as_timeout_block(self):
        detector = BlockDetector()
        text = """
        <html><head><title>CloakBrowser Unavailable</title></head>
        <body>RUNTIME_MISSING_MODULE cloakbrowser browser path unavailable</body></html>
        """
        blocked, block_type = detector.detect(
            200, text, len(text), BlockDetectionContext(page_pattern="search")
        )
        assert blocked is True
        assert block_type == BlockType.HTTP_TIMEOUT

    def test_walmart_robot_or_human_page_is_treated_as_bot_block(self):
        detector = BlockDetector()
        text = (
            "<html><head><title>Robot or human?</title></head><body>Robot or human?</body></html>"
        )
        blocked, block_type = detector.detect(
            200, text, len(text), BlockDetectionContext(page_pattern="search")
        )
        assert blocked is True
        assert block_type == BlockType.BOT_DETECTED
