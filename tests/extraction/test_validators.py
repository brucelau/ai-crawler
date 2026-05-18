"""Tests for validators - Pydantic validation for LLM outputs."""

import pytest
from ai_crawler.extraction.analysis.validators import (
    SelectorResult,
    BlockResult,
    ThresholdResult,
    URLDiscoveryResult,
    HumanBehaviorResult,
    validate_selector,
    validate_block,
    validate_threshold,
    validate_url_discovery,
    validate_human_behavior,
)


class TestSelectorResult:
    """SelectorResult should hold CSS selector extraction results."""

    def test_default_values(self):
        """Default values are sensible defaults."""
        result = SelectorResult()
        assert result.site == ""
        assert result.page_type == "search"
        assert result.list_container == ""

    def test_with_values(self):
        """Can be created with full values."""
        result = SelectorResult(
            site="amazon",
            page_type="search",
            title_selector="h2",
            price_selector=".price",
        )
        assert result.site == "amazon"
        assert result.title_selector == "h2"


class TestBlockResult:
    """BlockResult should hold block detection results."""

    def test_default_block_type(self):
        """Default block_type is unknown."""
        result = BlockResult()
        assert result.block_type == "unknown"

    def test_default_suggested_action(self):
        """Default suggested_action is retry_same."""
        result = BlockResult()
        assert result.suggested_action == "retry_same"

    def test_with_values(self):
        """Can be created with full values."""
        result = BlockResult(
            block_type="captcha",
            reasoning="CAPTCHA detected",
            suggested_action="skip",
        )
        assert result.block_type == "captcha"
        assert result.suggested_action == "skip"


class TestThresholdResult:
    """ThresholdResult should hold dynamic threshold recommendations."""

    def test_default_values(self):
        """Default timeout values are 30 seconds."""
        result = ThresholdResult()
        assert result.request_timeout == 30.0
        assert result.page_load_timeout == 30.0

    def test_default_delay(self):
        """Default delay is 3-8 seconds."""
        result = ThresholdResult()
        assert result.delay_after == [3, 8]


class TestURLDiscoveryResult:
    """URLDiscoveryResult should hold URL pattern discovery results."""

    def test_default_search_param(self):
        """Default search_param is q."""
        result = URLDiscoveryResult()
        assert result.search_param == "q"

    def test_default_page_param(self):
        """Default page_param is page."""
        result = URLDiscoveryResult()
        assert result.page_param == "page"

    def test_default_uses_js_rendering(self):
        """Default uses_js_rendering is True."""
        result = URLDiscoveryResult()
        assert result.uses_js_rendering is True


class TestHumanBehaviorResult:
    """HumanBehaviorResult should hold human behavior pattern results."""

    def test_default_scroll_strategy(self):
        """Default scroll_strategy is mixed."""
        result = HumanBehaviorResult()
        assert result.scroll_strategy == "mixed"

    def test_default_phases(self):
        """Default scroll_phases is empty list."""
        result = HumanBehaviorResult()
        assert result.scroll_phases == []


class TestValidateSelector:
    """validate_selector should convert raw dict to SelectorResult."""

    def test_valid_dict_returns_selector_result(self):
        """Valid dict creates SelectorResult."""
        raw = {"site": "amazon", "title_selector": "h1"}
        result = validate_selector(raw)
        assert isinstance(result, SelectorResult)
        assert result.site == "amazon"

    def test_invalid_dict_returns_default(self):
        """Invalid dict returns default SelectorResult."""
        raw = {"invalid": "data"}
        result = validate_selector(raw)
        assert isinstance(result, SelectorResult)
        assert result.site == ""


class TestValidateBlock:
    """validate_block should convert raw dict to BlockResult."""

    def test_valid_dict_returns_block_result(self):
        """Valid dict creates BlockResult."""
        raw = {"block_type": "captcha", "reasoning": "CAPTCHA found"}
        result = validate_block(raw)
        assert isinstance(result, BlockResult)
        assert result.block_type == "captcha"

    def test_missing_fields_uses_defaults(self):
        """Missing fields use defaults."""
        raw = {}
        result = validate_block(raw)
        assert result.block_type == "unknown"
        assert result.suggested_action == "retry_same"

    def test_partial_dict_preserves_values(self):
        """Partial dict preserves provided values."""
        raw = {"block_type": "http_403"}
        result = validate_block(raw)
        assert result.block_type == "http_403"


class TestValidateThreshold:
    """validate_threshold should convert raw dict to ThresholdResult."""

    def test_valid_dict_returns_threshold_result(self):
        """Valid dict creates ThresholdResult."""
        raw = {"request_timeout": 45.0, "page_load_timeout": 60.0}
        result = validate_threshold(raw)
        assert result.request_timeout == 45.0
        assert result.page_load_timeout == 60.0

    def test_delay_as_string_parsed(self):
        """Delay as JSON string is parsed."""
        raw = {"delay_after": "[5, 10]"}
        result = validate_threshold(raw)
        assert result.delay_after == [5, 10]

    def test_delay_as_list_preserved(self):
        """Delay as list is preserved."""
        raw = {"delay_after": [10, 20]}
        result = validate_threshold(raw)
        assert result.delay_after == [10, 20]

    def test_invalid_returns_defaults(self):
        """Invalid data returns default ThresholdResult."""
        raw = {"invalid": "data"}
        result = validate_threshold(raw)
        assert result.request_timeout == 30.0


class TestValidateUrlDiscovery:
    """validate_url_discovery should convert raw dict to URLDiscoveryResult."""

    def test_valid_dict_returns_url_discovery_result(self):
        """Valid dict creates URLDiscoveryResult."""
        raw = {
            "site": "amazon",
            "search_url_pattern": "https://amazon.com/s?k={query}",
        }
        result = validate_url_discovery(raw)
        assert result.site == "amazon"
        assert "amazon.com" in result.search_url_pattern

    def test_missing_fields_use_defaults(self):
        """Missing fields use defaults."""
        raw = {}
        result = validate_url_discovery(raw)
        assert result.search_param == "q"
        assert result.page_param == "page"


class TestValidateHumanBehavior:
    """validate_human_behavior should convert raw dict to HumanBehaviorResult."""

    def test_valid_dict_returns_human_behavior_result(self):
        """Valid dict creates HumanBehaviorResult."""
        raw = {
            "scroll_strategy": "gradual",
            "scroll_phases": [{"start_y": 0, "end_y": 500}],
        }
        result = validate_human_behavior(raw)
        assert result.scroll_strategy == "gradual"
        assert len(result.scroll_phases) == 1

    def test_phases_as_string_parsed(self):
        """Phases as JSON string is parsed."""
        raw = {"scroll_phases": '[{"start_y": 0}]'}
        result = validate_human_behavior(raw)
        assert len(result.scroll_phases) == 1

    def test_invalid_returns_defaults(self):
        """Invalid data returns default HumanBehaviorResult."""
        raw = {"invalid": "data"}
        result = validate_human_behavior(raw)
        assert result.scroll_strategy == "mixed"
