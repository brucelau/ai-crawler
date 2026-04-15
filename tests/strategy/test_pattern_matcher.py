"""Tests for PatternMatcher - URL to page pattern detection."""

import pytest
from ai_crawler.core.strategy import PagePattern, PatternMatcher


class TestPatternMatcher:
    """PatternMatcher.detect() should map URLs to correct PagePattern."""

    # Amazon patterns
    def test_amazon_search_s(self):
        """Amazon /s? URL → SEARCH."""
        assert (
            PatternMatcher.detect("amazon", "https://www.amazon.com/s?k=inflatable")
            == PagePattern.SEARCH
        )

    def test_amazon_search_s_with_page(self):
        """Amazon /s? URL with page param → SEARCH."""
        assert (
            PatternMatcher.detect("amazon", "https://www.amazon.com/s?k=costume&page=2")
            == PagePattern.SEARCH
        )

    def test_amazon_search_s_slash(self):
        """Amazon /s/? URL → SEARCH."""
        assert (
            PatternMatcher.detect("amazon", "https://www.amazon.com/s/?k=inflatable")
            == PagePattern.SEARCH
        )

    def test_amazon_search_gp_search(self):
        """Amazon /gp/search → SEARCH."""
        assert (
            PatternMatcher.detect("amazon", "https://www.amazon.com/gp/search")
            == PagePattern.SEARCH
        )

    def test_amazon_detail_dp(self):
        """Amazon /dp/ product URL → DETAIL."""
        assert (
            PatternMatcher.detect("amazon", "https://www.amazon.com/dp/B08N5WRWNW")
            == PagePattern.DETAIL
        )

    def test_amazon_detail_gp_product(self):
        """Amazon /gp/product/ URL → DETAIL."""
        assert (
            PatternMatcher.detect("amazon", "https://www.amazon.com/gp/product/B08N5WRWNW")
            == PagePattern.DETAIL
        )

    def test_amazon_seller_stores(self):
        """Amazon /stores/ URL → SELLER."""
        assert (
            PatternMatcher.detect("amazon", "https://www.amazon.com/stores/seller123")
            == PagePattern.SELLER
        )

    def test_amazon_seller_sp(self):
        """Amazon /sp/ URL (seller page, not search) → SELLER."""
        assert (
            PatternMatcher.detect("amazon", "https://www.amazon.com/sp/partnerid123")
            == PagePattern.SELLER
        )

    def test_amazon_review_product_reviews(self):
        """Amazon /product-reviews/ URL → REVIEW."""
        assert (
            PatternMatcher.detect("amazon", "https://www.amazon.com/product-reviews/B08N5WRWNW")
            == PagePattern.REVIEW
        )

    def test_amazon_review_hz(self):
        """Amazon /hz/r/cr/ URL → REVIEW."""
        assert (
            PatternMatcher.detect("amazon", "https://www.amazon.com/hz/r/cr/1234567")
            == PagePattern.REVIEW
        )

    # Walmart patterns
    def test_walmart_search(self):
        """Walmart /search? URL → SEARCH."""
        assert (
            PatternMatcher.detect("walmart", "https://www.walmart.com/search?q=inflatable")
            == PagePattern.SEARCH
        )

    def test_walmart_search_php(self):
        """Walmart /search.php URL → SEARCH."""
        assert (
            PatternMatcher.detect("walmart", "https://www.walmart.com/search.php?q=costume")
            == PagePattern.SEARCH
        )

    def test_walmart_detail_ip(self):
        """Walmart /ip/ URL → DETAIL."""
        assert (
            PatternMatcher.detect(
                "walmart", "https://www.walmart.com/ip/Inflatable-Costume/123456789"
            )
            == PagePattern.DETAIL
        )

    def test_walmart_detail_dash_ip(self):
        """Walmart /-/ip/ URL → DETAIL."""
        assert (
            PatternMatcher.detect("walmart", "https://www.walmart.com/-/ip/Product-Name/987654321")
            == PagePattern.DETAIL
        )

    def test_walmart_seller(self):
        """Walmart /seller/ URL → SELLER."""
        assert (
            PatternMatcher.detect("walmart", "https://www.walmart.com/seller/sellername")
            == PagePattern.SELLER
        )

    # Target patterns
    def test_target_search_s(self):
        """Target /s? URL → SEARCH."""
        assert (
            PatternMatcher.detect("target", "https://www.target.com/s?searchTerm=inflatable")
            == PagePattern.SEARCH
        )

    def test_target_search_searchTerm(self):
        """Target /search? URL → SEARCH."""
        assert (
            PatternMatcher.detect("target", "https://www.target.com/search?q=costume")
            == PagePattern.SEARCH
        )

    def test_target_detail_dash_a(self):
        """Target /-/A- URL → DETAIL."""
        assert (
            PatternMatcher.detect("target", "https://www.target.com/-/A-12345678")
            == PagePattern.DETAIL
        )

    def test_target_detail_p(self):
        """Target /p/ URL → DETAIL."""
        assert (
            PatternMatcher.detect("target", "https://www.target.com/p/product-name")
            == PagePattern.DETAIL
        )

    # eBay patterns
    def test_ebay_search_sch(self):
        """eBay /sch/i.html URL → SEARCH."""
        assert (
            PatternMatcher.detect("ebay", "https://www.ebay.com/sch/i.html?_nkw=inflatable")
            == PagePattern.SEARCH
        )

    def test_ebay_search_sch_page(self):
        """eBay /sch/ with page → SEARCH."""
        assert (
            PatternMatcher.detect("ebay", "https://www.ebay.com/sch/?_nkw=costume&page=1")
            == PagePattern.SEARCH
        )

    def test_ebay_detail_itm(self):
        """eBay /itm/ URL → DETAIL."""
        assert (
            PatternMatcher.detect("ebay", "https://www.ebay.com/itm/123456789012")
            == PagePattern.DETAIL
        )

    def test_ebay_detail_itm_with_name(self):
        """eBay /itm/ with product name → DETAIL."""
        assert (
            PatternMatcher.detect(
                "ebay", "https://www.ebay.com/itm/Inflatabl-Costume-Adj-123456789012"
            )
            == PagePattern.DETAIL
        )

    def test_ebay_seller_str(self):
        """eBay /str/ URL → SELLER."""
        assert (
            PatternMatcher.detect("ebay", "https://www.ebay.com/str/mystore") == PagePattern.SELLER
        )

    # Unknown / fallback
    def test_unknown_url_returns_unknown(self):
        """Unrecognized URL → UNKNOWN."""
        assert (
            PatternMatcher.detect("amazon", "https://www.amazon.com/unknown/path")
            == PagePattern.UNKNOWN
        )

    def test_unknown_site_returns_unknown(self):
        """Unknown site → UNKNOWN."""
        assert (
            PatternMatcher.detect("unknownsite", "https://www.unknownsite.com/s?k=test")
            == PagePattern.UNKNOWN
        )

    def test_case_insensitive_matching(self):
        """URL matching should be case insensitive."""
        assert (
            PatternMatcher.detect("amazon", "https://www.amazon.com/DP/B08N5WRWNW")
            == PagePattern.DETAIL
        )
        assert (
            PatternMatcher.detect("amazon", "https://www.amazon.com/DP/b08n5wrwnw")
            == PagePattern.DETAIL
        )

    def test_empty_site_returns_unknown(self):
        """Empty site name → UNKNOWN."""
        assert PatternMatcher.detect("", "https://example.com/s?k=test") == PagePattern.UNKNOWN

    def test_partial_match_not_triggered(self):
        """Partial keyword matches should not trigger (e.g., /dp/ in query string)."""
        url = "https://www.amazon.com/s?k=dp&searchType=detail"
        assert PatternMatcher.detect("amazon", url) == PagePattern.SEARCH
