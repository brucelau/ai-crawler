"""Tests for LLMExtractor - LLM-based CSS selector extraction."""

import pytest
from unittest.mock import Mock, patch, MagicMock

pytest.importorskip("bs4")

from ai_crawler.core.llm.llm_extractor import LLMExtractor, extract_with_llm_page


class TestLLMExtractorInit:
    """LLMExtractor initialization."""

    def test_singleton_pattern(self):
        """LLMExtractor uses singleton pattern."""
        extractor1 = LLMExtractor()
        extractor2 = LLMExtractor()
        assert extractor1 is extractor2

    def test_initialized_flag(self):
        """Sets initialized flag."""
        extractor = LLMExtractor()
        assert hasattr(extractor, "_initialized")


class TestLLMExtractorCacheKey:
    """LLMExtractor._cache_key() should generate cache keys."""

    def test_cache_key_format(self):
        """Cache key is site:page_type."""
        extractor = LLMExtractor()
        key = extractor._cache_key("amazon", "search")
        assert key == "amazon:search"

    def test_cache_key_different_page_types(self):
        """Different page types produce different keys."""
        extractor = LLMExtractor()
        key1 = extractor._cache_key("amazon", "search")
        key2 = extractor._cache_key("amazon", "detail")
        assert key1 != key2


class TestLLMExtractorCacheValidity:
    """LLMExtractor._is_cache_valid() should check cache TTL."""

    def test_cache_invalid_when_empty(self):
        """Cache is invalid when key not in cache."""
        extractor = LLMExtractor()
        extractor._cache.clear()
        assert extractor._is_cache_valid("amazon", "search") is False

    def test_cache_valid_within_ttl(self):
        """Cache is valid when within TTL."""
        extractor = LLMExtractor()
        extractor._cache.clear()
        extractor._cache["amazon:search"] = {"_cached_at": 9999999999}
        result = extractor._is_cache_valid("amazon", "search")
        assert result is True

    def test_cache_invalid_after_ttl(self):
        """Cache is invalid after TTL expires."""
        import time

        extractor = LLMExtractor()
        extractor._cache.clear()
        old_time = time.time() - extractor._cache_ttl - 1
        extractor._cache["amazon:search"] = {"_cached_at": old_time}
        assert extractor._is_cache_valid("amazon", "search") is False


class TestLLMExtractorDefaultSelectors:
    """LLMExtractor._default_selectors() should return fallback selectors."""

    def test_amazon_has_defaults(self):
        """Amazon has predefined selectors."""
        result = LLMExtractor()._default_selectors("amazon", "search")
        assert result["site"] == "amazon"
        assert result["page_type"] == "search"
        assert "title_selector" in result
        assert "price_selector" in result

    def test_walmart_has_defaults(self):
        """Walmart has predefined selectors."""
        result = LLMExtractor()._default_selectors("walmart", "search")
        assert result["site"] == "walmart"

    def test_unknown_site_has_default_selectors(self):
        """Unknown site gets generic default selectors."""
        result = LLMExtractor()._default_selectors("unknownsite", "search")
        assert result["site"] == "unknownsite"
        assert result["list_container"] != ""


class TestLLMExtractorGenerateSelectors:
    """LLMExtractor._generate_selectors() should use LLM when available."""

    def test_returns_defaults_when_no_llm(self):
        """Returns default selectors when LLM not available."""
        extractor = LLMExtractor()
        with patch.object(extractor, "_get_dspy_extractor", return_value=None):
            result = extractor._generate_selectors("amazon", "search", "<html></html>")
            assert result["site"] == "amazon"

    def test_uses_dspy_extractor_when_available(self):
        """Uses DSPy extractor when configured."""
        extractor = LLMExtractor()
        mock_result = Mock()
        mock_result.__dict__ = {"site": "amazon", "page_type": "search", "title_selector": "h1"}
        mock_predictor = Mock(return_value=mock_result)
        with patch.object(extractor, "_get_dspy_extractor", return_value=mock_predictor):
            with patch("ai_crawler.core.llm.llm_extractor.validate_selector") as mock_validate:
                mock_validate.return_value = Mock(model_dump=lambda: {"site": "amazon"})
                result = extractor._generate_selectors(
                    "amazon", "search", "<html><h1>Test</h1></html>"
                )
                assert "site" in result

    def test_passes_semantic_sample_to_dspy_extractor(self):
        extractor = LLMExtractor()
        mock_result = Mock()
        mock_result.__dict__ = {"site": "amazon", "page_type": "search", "title_selector": "h1"}
        mock_predictor = Mock(return_value=mock_result)
        with patch.object(extractor, "_get_dspy_extractor", return_value=mock_predictor):
            with patch("ai_crawler.core.llm.llm_extractor.validate_selector") as mock_validate:
                mock_validate.return_value = Mock(model_dump=lambda: {"site": "amazon"})
                extractor._generate_selectors(
                    "amazon",
                    "search",
                    "<html><h1>Test</h1></html>",
                    semantic_sample="semantic summary",
                )
                assert mock_predictor.call_args.kwargs["semantic_sample"] == "semantic summary"


class TestLLMExtractorGetSelectors:
    """LLMExtractor.get_selectors() should return cached or fresh selectors."""

    def test_returns_cached_when_valid(self):
        """Returns cached selectors when cache is valid."""
        import time

        extractor = LLMExtractor()
        extractor._cache.clear()
        extractor._cache["amazon:search"] = {
            "_cached_at": time.time(),
            "site": "amazon",
            "title_selector": "h1",
        }
        result = extractor.get_selectors("amazon", "search")
        assert result["title_selector"] == "h1"

    def test_regenerates_when_force_regenerate(self):
        """Regenerates selectors when force_regenerate=True."""
        import time

        extractor = LLMExtractor()
        extractor._cache.clear()
        extractor._cache["amazon:search"] = {
            "_cached_at": time.time(),
            "site": "amazon",
            "title_selector": "old",
        }
        with patch.object(
            extractor,
            "_generate_selectors",
            return_value={"site": "amazon", "title_selector": "new"},
        ):
            with patch("ai_crawler.core.llm.llm_extractor.template_store"):
                result = extractor.get_selectors("amazon", "search", force_regenerate=True)
                assert result["title_selector"] == "new"

    def test_loads_from_template_store_when_available(self):
        """Loads from template store if no cache but template exists."""
        extractor = LLMExtractor()
        extractor._cache.clear()
        mock_template = {"site": "amazon", "title_selector": "from_template"}
        with patch("ai_crawler.core.llm.llm_extractor.template_store") as mock_ts:
            mock_ts.load.return_value = mock_template
            result = extractor.get_selectors("amazon", "search", html_sample="<html></html>")
            assert result["title_selector"] == "from_template"


class TestLLMExtractorExtract:
    """LLMExtractor.extract() should parse HTML and extract products."""

    def test_extract_returns_list(self):
        """extract() returns a list of products."""
        html = "<html><body><h2>Test Product</h2><span>$19.99</span></body></html>"
        result = LLMExtractor().extract(html, "amazon", "search", "http://example.com")
        assert isinstance(result, list)

    def test_extract_with_empty_html(self):
        """Extract with empty HTML returns empty list."""
        result = LLMExtractor().extract("", "amazon", "search", "http://example.com")
        assert result == []

    def test_extract_handles_invalid_html_gracefully(self):
        """Handles malformed HTML without crashing."""
        html = "<html><body><ul><li>Item 1<li>Item 2</ul></body>"  # unclosed tags
        result = LLMExtractor().extract(html, "amazon", "search", "http://example.com")
        assert isinstance(result, list)

    def test_extract_respects_product_limit(self):
        """Extract limits products to reasonable number."""
        html = "<html><body>"
        for i in range(100):
            html += f'<li class="product"><h2>Product {i}</h2><span>$10</span></li>'
        html += "</body></html>"
        extractor = LLMExtractor()
        extractor._cache.clear()
        result = extractor.extract(html, "amazon", "search", "http://example.com")
        assert len(result) <= 20


class TestExtractWithLlmFunction:
    """extract_with_llm() module function should delegate to LLMExtractor."""

    def test_extract_with_llm_exists(self):
        """Module function exists."""
        from ai_crawler.core.llm.llm_extractor import extract_with_llm

        assert callable(extract_with_llm)

    def test_extract_with_llm_returns_list(self):
        """Returns list of products."""
        from ai_crawler.core.llm.llm_extractor import extract_with_llm

        result = extract_with_llm("<html></html>", "amazon", "search", "http://example.com")
        assert isinstance(result, list)

    def test_extract_with_llm_page_exists(self):
        assert callable(extract_with_llm_page)


class TestLLMExtractorAXTreeSemanticSample:
    def test_extract_with_page_builds_axtree_semantic_sample(self):
        extractor = LLMExtractor()
        html = "<html><body><h2>Test Product</h2><span>$19.99</span></body></html>"
        fake_page = object()

        with patch(
            "ai_crawler.core.llm.llm_extractor.build_axtree_selector_sample",
            return_value="semantic",
        ):
            with patch.object(
                extractor,
                "get_selectors",
                return_value=extractor._default_selectors("amazon", "search"),
            ) as mock_get:
                result = extractor.extract_with_page(
                    html, fake_page, "amazon", "search", "http://example.com"
                )
                assert isinstance(result, list)
                assert mock_get.call_args.kwargs["semantic_sample"] == "semantic"

    def test_extract_without_page_uses_empty_semantic_sample(self):
        extractor = LLMExtractor()
        html = "<html><body><h2>Test Product</h2><span>$19.99</span></body></html>"

        with patch.object(
            extractor,
            "get_selectors",
            return_value=extractor._default_selectors("amazon", "search"),
        ) as mock_get:
            extractor.extract_with_page(html, None, "amazon", "search", "http://example.com")
            assert mock_get.call_args.kwargs["semantic_sample"] == ""


class TestLLMExtractorSearchFiltering:
    def test_filters_generic_target_search_result(self):
        extractor = LLMExtractor()
        html = """
        <html><body>
          <a href="/s?searchTerm=chair"><span>Type</span><span>$143.98</span></a>
        </body></html>
        """
        selectors = {
            "list_container": "a",
            "product_selector": "a",
            "title_selector": "span:first-child",
            "price_selector": "span:last-child",
            "link_selector": "a",
        }

        with patch.object(extractor, "get_selectors", return_value=selectors):
            products = extractor.extract_with_page(
                html,
                None,
                "target",
                "search",
                "https://www.target.com/s?searchTerm=chair",
            )

        assert products == []

    def test_keeps_valid_target_search_result(self):
        extractor = LLMExtractor()
        html = """
        <html><body>
          <div class="card">
            <a href="/p/patio-chair/-/A-123"><span>Outdoor Patio Chair</span><span>$143.98</span></a>
          </div>
        </body></html>
        """
        selectors = {
            "list_container": ".card",
            "product_selector": ".card",
            "title_selector": "span:first-child",
            "price_selector": "span:last-child",
            "link_selector": "a",
        }

        with patch.object(extractor, "get_selectors", return_value=selectors):
            products = extractor.extract_with_page(
                html,
                None,
                "target",
                "search",
                "https://www.target.com/s?searchTerm=chair",
            )

        assert len(products) == 1
        assert products[0].title == "Outdoor Patio Chair"
