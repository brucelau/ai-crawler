"""Tests for InteractiveSearcher.perform_search."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from ai_crawler.browser.interaction import InteractiveSearcher


class TestInteractiveSearcherPerformSearch:
    """Unit tests for InteractiveSearcher.perform_search."""

    @pytest.fixture
    def site_config(self):
        return {
            "site": "example",
            "homepage_url": "https://example.com",
            "search_input_selector": "#search-input",
            "search_button_selector": "#search-btn",
        }

    @pytest.fixture
    def mock_page(self):
        page = MagicMock()
        return page

    def test_perform_search_success(self, mock_page, site_config):
        """Successful search navigates to homepage, types query, and submits."""
        searcher = InteractiveSearcher(mock_page, site_config)
        result = searcher.perform_search("test product")

        assert result is True
        mock_page.goto.assert_called_once_with(
            "https://example.com", wait_until="domcontentloaded", timeout=45000
        )
        mock_page.wait_for_selector.assert_called_with("#search-input", timeout=10000)
        mock_page.click.assert_called()

    def test_perform_search_missing_homepage_url(self, mock_page):
        """Returns False when homepage_url is missing."""
        config = {"site": "example", "search_input_selector": "#input"}
        searcher = InteractiveSearcher(mock_page, config)
        result = searcher.perform_search("query")

        assert result is False
        mock_page.goto.assert_not_called()

    def test_perform_search_missing_input_selector(self, mock_page):
        """Returns False when search_input_selector is missing."""
        config = {"site": "example", "homepage_url": "https://example.com"}
        searcher = InteractiveSearcher(mock_page, config)
        result = searcher.perform_search("query")

        assert result is False

    def test_perform_search_goto_error(self, mock_page, site_config):
        """Returns False when page.goto raises an error."""
        mock_page.goto.side_effect = RuntimeError("Navigation timeout")
        searcher = InteractiveSearcher(mock_page, site_config)
        result = searcher.perform_search("test")

        assert result is False

    def test_perform_search_types_characters(self, mock_page, site_config):
        """Search types each character individually with random delays."""
        searcher = InteractiveSearcher(mock_page, site_config)
        searcher.perform_search("ab")

        # Each character should be typed via keyboard.type
        assert mock_page.keyboard.type.call_count >= 2

    def test_perform_search_without_button_selector(self, mock_page, site_config):
        """When button_selector is absent, presses Enter to submit."""
        config = {
            "site": "example",
            "homepage_url": "https://example.com",
            "search_input_selector": "#input",
        }
        searcher = InteractiveSearcher(mock_page, config)
        with patch("random.random", return_value=0.1):  # < 0.3, use button
            searcher.perform_search("query")

    def test_perform_search_press_enter(self, mock_page, site_config):
        """When random > 0.3 or no button, Enter is pressed."""
        config = {
            "site": "example",
            "homepage_url": "https://example.com",
            "search_input_selector": "#input",
        }
        searcher = InteractiveSearcher(mock_page, config)
        with patch("random.random", return_value=0.5):  # > 0.3, use Enter
            searcher.perform_search("query")
            mock_page.keyboard.press.assert_called_with("Enter")
