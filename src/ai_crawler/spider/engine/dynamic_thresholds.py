from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from ai_crawler.config import config
from ai_crawler.spider.extraction.analysis.validators import validate_threshold


@dataclass
class SiteMetrics:
    response_times: list[float] = field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    last_updated: float = field(default_factory=time.time)
    total_requests: int = 0

    def avg_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)

    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        if total == 0:
            return 1.0
        return self.success_count / total

    def to_dict(self) -> dict:
        return {
            "avg_response_time": self.avg_response_time(),
            "success_rate": self.success_rate(),
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "total_requests": self.total_requests,
        }


class DynamicThresholdOptimizer:
    _instance: Optional["DynamicThresholdOptimizer"] = None
    _llm_cache: dict[str, tuple[dict, float]] = {}
    _llm_cache_ttl: float = 86400.0

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._metrics: dict[str, SiteMetrics] = defaultdict(SiteMetrics)
            self._dspy_optimizer = None
            self._initialized = True

    def _llm_cache_key(self, site: str, page_type: str = "search") -> str:
        return f"{site}:{page_type}"

    def _is_llm_cache_valid(self, site: str, page_type: str = "search") -> bool:
        key = self._llm_cache_key(site, page_type)
        if key not in self._llm_cache:
            return False
        _, cached_time = self._llm_cache[key]
        return (time.time() - cached_time) < self._llm_cache_ttl

    def _get_dspy_optimizer(self):
        if not config.has_llm():
            return None
        if self._dspy_optimizer is None:
            from ai_crawler.spider.llm.dspy_model import ThresholdOptimizer

            self._dspy_optimizer = ThresholdOptimizer()
        return self._dspy_optimizer

    def record_success(self, site: str, response_time: float) -> None:
        metrics = self._metrics[site]
        metrics.response_times.append(response_time)
        if len(metrics.response_times) > 50:
            metrics.response_times = metrics.response_times[-50:]
        metrics.success_count += 1
        metrics.total_requests += 1
        metrics.last_updated = time.time()

    def record_failure(self, site: str) -> None:
        metrics = self._metrics[site]
        metrics.failure_count += 1
        metrics.total_requests += 1
        metrics.last_updated = time.time()

    def get_thresholds(self, site: str) -> dict:
        metrics = self._metrics[site]
        if metrics.total_requests < 5:
            return self._default_thresholds()

        avg_time = metrics.avg_response_time()
        success_rate = metrics.success_rate()
        base_timeout = config.REQUEST_TIMEOUT
        base_page_load = config.PAGE_LOAD_TIMEOUT

        if success_rate < 0.5:
            timeout_mult = 2.0
            delay_mult = 1.5
        elif success_rate < 0.8:
            timeout_mult = 1.5
            delay_mult = 1.2
        else:
            timeout_mult = 1.0
            delay_mult = 1.0

        if avg_time > 5.0:
            timeout_mult *= 1.3
        elif avg_time < 2.0:
            timeout_mult *= 0.9

        recommended_request_timeout = max(5.0, min(60.0, base_timeout * timeout_mult))
        recommended_page_load_timeout = max(10.0, min(120.0, base_page_load * timeout_mult))

        delay_min = max(1, int(3 * delay_mult))
        delay_max = max(3, int(8 * delay_mult))

        return {
            "request_timeout": recommended_request_timeout,
            "page_load_timeout": recommended_page_load_timeout,
            "delay_after": (delay_min, delay_max),
            "confidence": min(1.0, metrics.total_requests / 20.0),
            "strategy": "heuristic_adjusted",
        }

    def _default_thresholds(self) -> dict:
        return {
            "request_timeout": config.REQUEST_TIMEOUT,
            "page_load_timeout": config.PAGE_LOAD_TIMEOUT,
            "delay_after": (3, 8),
            "confidence": 0.0,
            "strategy": "default",
        }

    def get_site_profile(self, site: str) -> dict:
        metrics = self._metrics[site]
        return {
            "site": site,
            "metrics": metrics.to_dict(),
            "thresholds": self.get_thresholds(site),
            "last_updated": metrics.last_updated,
        }

    def suggest_thresholds_via_llm(
        self, site: str, page_type: str = "search", html_sample: str = ""
    ) -> dict:
        if self._is_llm_cache_valid(site, page_type):
            cached, _ = self._llm_cache[self._llm_cache_key(site, page_type)]
            return cached

        optimizer = self._get_dspy_optimizer()
        if not optimizer:
            return self.get_thresholds(site)

        metrics = self._metrics[site]
        if metrics.total_requests < 5:
            return self.get_thresholds(site)

        try:
            raw_result = optimizer(
                site=site,
                page_type=page_type,
                avg_response_time=metrics.avg_response_time(),
                success_rate=metrics.success_rate(),
                total_requests=metrics.total_requests,
                current_timeout=config.REQUEST_TIMEOUT,
                current_page_load_timeout=config.PAGE_LOAD_TIMEOUT,
                html_sample=html_sample[:2000] if html_sample else "",
            )

            result = validate_threshold(raw_result.__dict__)
            thresholds = {
                "request_timeout": result.request_timeout,
                "page_load_timeout": result.page_load_timeout,
                "delay_after": tuple(result.delay_after),
                "confidence": 0.8,
                "strategy": "llm_suggested",
                "reasoning": result.reasoning,
            }
            self._llm_cache[self._llm_cache_key(site, page_type)] = (thresholds, time.time())
            return thresholds
        except Exception:
            return self.get_thresholds(site)

    def get_all_site_stats(self) -> dict:
        return {site: self.get_site_profile(site) for site in self._metrics}


dynamic_optimizer = DynamicThresholdOptimizer()


def get_dynamic_thresholds(site: str) -> dict:
    return dynamic_optimizer.get_thresholds(site)


def record_success(site: str, response_time: float) -> None:
    dynamic_optimizer.record_success(site, response_time)


def record_failure(site: str) -> None:
    dynamic_optimizer.record_failure(site)
