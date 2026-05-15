"""Tests for DynamicThresholdOptimizer and SiteMetrics."""

import pytest
import time
from unittest.mock import Mock, patch

from ai_crawler.spider.engine.dynamic_thresholds import (
    SiteMetrics,
    DynamicThresholdOptimizer,
    dynamic_optimizer,
    get_dynamic_thresholds,
    record_success,
    record_failure,
)


class TestSiteMetrics:
    """SiteMetrics dataclass for tracking site performance."""

    def test_init_defaults(self):
        """Initializes with default values."""
        metrics = SiteMetrics()
        assert metrics.success_count == 0
        assert metrics.failure_count == 0
        assert len(metrics.response_times) == 0

    def test_avg_response_time_empty(self):
        """Returns 0 when no response times."""
        metrics = SiteMetrics()
        assert metrics.avg_response_time() == 0.0

    def test_avg_response_time_with_data(self):
        """Calculates average correctly."""
        metrics = SiteMetrics()
        metrics.response_times = [1.0, 2.0, 3.0]
        assert metrics.avg_response_time() == 2.0

    def test_success_rate_no_data(self):
        """Returns 1.0 when no data."""
        metrics = SiteMetrics()
        assert metrics.success_rate() == 1.0

    def test_success_rate_with_failures(self):
        """Calculates success rate correctly."""
        metrics = SiteMetrics()
        metrics.success_count = 8
        metrics.failure_count = 2
        assert metrics.success_rate() == 0.8

    def test_to_dict(self):
        """Returns dictionary representation."""
        metrics = SiteMetrics()
        metrics.success_count = 5
        metrics.failure_count = 1
        d = metrics.to_dict()
        assert "avg_response_time" in d
        assert "success_rate" in d


class TestDynamicThresholdOptimizerInit:
    """DynamicThresholdOptimizer initialization."""

    def test_singleton_pattern(self):
        """Uses singleton pattern."""
        opt1 = DynamicThresholdOptimizer()
        opt2 = DynamicThresholdOptimizer()
        assert opt1 is opt2


class TestDynamicThresholdOptimizerRecord:
    """Recording success/failure."""

    def test_record_success(self):
        """Records successful request."""
        opt = DynamicThresholdOptimizer()
        opt._metrics.clear()
        opt.record_success("amazon", 1.5)
        assert opt._metrics["amazon"].success_count == 1

    def test_record_failure(self):
        """Records failed request."""
        opt = DynamicThresholdOptimizer()
        opt._metrics.clear()
        opt.record_failure("amazon")
        assert opt._metrics["amazon"].failure_count == 1

    def test_response_time_trimmed(self):
        """Response times trimmed to 50."""
        opt = DynamicThresholdOptimizer()
        opt._metrics.clear()
        for i in range(60):
            opt.record_success("amazon", float(i))
        assert len(opt._metrics["amazon"].response_times) <= 50


class TestDynamicThresholdOptimizerGetThresholds:
    """Getting threshold recommendations."""

    def test_returns_defaults_when_insufficient_data(self):
        """Returns defaults when < 5 requests."""
        opt = DynamicThresholdOptimizer()
        opt._metrics.clear()
        result = opt.get_thresholds("amazon")
        assert "request_timeout" in result
        assert result["strategy"] == "default"

    def test_heuristic_adjusted_low_success_rate(self):
        """Adjusts thresholds for low success rate."""
        opt = DynamicThresholdOptimizer()
        opt._metrics.clear()
        for _ in range(10):
            opt.record_failure("amazon")
        result = opt.get_thresholds("amazon")
        assert result["strategy"] == "heuristic_adjusted"


class TestDynamicThresholdOptimizerLLMCaching:
    """LLM cache functionality."""

    def test_llm_cache_key(self):
        """Cache key format is site:page_type."""
        opt = DynamicThresholdOptimizer()
        key = opt._llm_cache_key("amazon", "search")
        assert key == "amazon:search"

    def test_llm_cache_invalid_when_empty(self):
        """Cache invalid when empty."""
        opt = DynamicThresholdOptimizer()
        opt._llm_cache.clear()
        assert opt._is_llm_cache_valid("amazon") is False

    def test_llm_cache_valid_within_ttl(self):
        """Cache valid within TTL."""
        opt = DynamicThresholdOptimizer()
        opt._llm_cache.clear()
        opt._llm_cache["amazon:search"] = ({}, time.time())
        assert opt._is_llm_cache_valid("amazon", "search") is True

    def test_llm_cache_invalid_after_ttl(self):
        """Cache invalid after TTL."""
        opt = DynamicThresholdOptimizer()
        opt._llm_cache.clear()
        old_time = time.time() - opt._llm_cache_ttl - 1
        opt._llm_cache["amazon:search"] = ({}, old_time)
        assert opt._is_llm_cache_valid("amazon", "search") is False


class TestDynamicThresholdOptimizerSuggestThresholds:
    """LLM-based threshold suggestion."""

    def test_returns_heuristic_when_no_llm(self):
        """Returns heuristic thresholds when LLM unavailable."""
        opt = DynamicThresholdOptimizer()
        opt._metrics.clear()
        for _ in range(10):
            opt.record_success("amazon", 2.0)
        with patch.object(opt, "_get_dspy_optimizer", return_value=None):
            result = opt.suggest_thresholds_via_llm("amazon")
            assert "request_timeout" in result


class TestDynamicThresholdOptimizerGetSiteProfile:
    """Getting site profile."""

    def test_returns_profile_dict(self):
        """Returns profile with metrics and thresholds."""
        opt = DynamicThresholdOptimizer()
        opt._metrics.clear()
        opt.record_success("amazon", 1.5)
        profile = opt.get_site_profile("amazon")
        assert "site" in profile
        assert "metrics" in profile
        assert "thresholds" in profile


class TestDynamicThresholdOptimizerGetAllSiteStats:
    """Getting all site stats."""

    def test_returns_dict(self):
        """Returns dictionary of all sites."""
        opt = DynamicThresholdOptimizer()
        opt._metrics.clear()
        opt.record_success("amazon", 1.5)
        stats = opt.get_all_site_stats()
        assert isinstance(stats, dict)
        assert "amazon" in stats


class TestModuleFunctions:
    """Module-level functions."""

    def test_get_dynamic_thresholds(self):
        """get_dynamic_thresholds is callable."""
        result = get_dynamic_thresholds("amazon")
        assert isinstance(result, dict)

    def test_record_success_function(self):
        """record_success is callable."""
        record_success("amazon", 1.5)

    def test_record_failure_function(self):
        """record_failure is callable."""
        record_failure("amazon")
