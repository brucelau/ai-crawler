from __future__ import annotations

import time
from typing import Optional

from ai_crawler.config import config
from ai_crawler.spider.extraction.analysis.validators import validate_url_discovery


class URLDiscovery:
    _instance: Optional["URLDiscovery"] = None
    _cache: dict[str, dict] = {}
    _cache_ttl: float = 86400.0

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._dspy_discoverer = None

    def _get_dspy_discoverer(self):
        if not config.has_llm():
            return None
        if self._dspy_discoverer is None:
            from ai_crawler.spider.llm.dspy_model import URLDiscoverer

            self._dspy_discoverer = URLDiscoverer()
        return self._dspy_discoverer

    def _is_cache_valid(self, site: str) -> bool:
        if site not in self._cache:
            return False
        cached_time = self._cache[site].get("_cached_at", 0)
        return (time.time() - cached_time) < self._cache_ttl

    def _discover_url_format(self, site: str, homepage_html: str) -> dict:
        discoverer = self._get_dspy_discoverer()
        if not discoverer:
            return self._default_url_format(site)

        try:
            raw_result = discoverer(site=site, homepage_html=homepage_html[:5000])
            result = validate_url_discovery(raw_result.__dict__)
            url_format = result.model_dump()
            url_format["_cached_at"] = time.time()
            return url_format
        except Exception:
            return self._default_url_format(site)

    def _default_url_format(self, site: str) -> dict:
        defaults = {
            "amazon": {
                "site": "amazon",
                "search_url_pattern": "https://www.amazon.com/s?k={query}",
                "search_param": "k",
                "page_param": "page",
                "product_url_pattern": "https://www.amazon.com/dp/{asin}",
                "uses_js_rendering": False,
            },
            "walmart": {
                "site": "walmart",
                "search_url_pattern": "https://www.walmart.com/search?q={query}",
                "search_param": "q",
                "page_param": "page",
                "product_url_pattern": "https://www.walmart.com/ip/{id}",
                "uses_js_rendering": True,
            },
            "target": {
                "site": "target",
                "search_url_pattern": "https://www.target.com/s?searchTerm={query}",
                "search_param": "searchTerm",
                "page_param": "page",
                "product_url_pattern": "https://www.target.com/p/{id}",
                "uses_js_rendering": True,
            },
        }
        result = defaults.get(
            site,
            {
                "site": site,
                "search_url_pattern": f"https://www.{site}.com/search?q={{query}}",
                "search_param": "q",
                "page_param": "page",
                "product_url_pattern": "",
                "uses_js_rendering": True,
            },
        ).copy()
        result["_cached_at"] = time.time()
        return result

    def get_url_format(self, site: str, homepage_html: str = "") -> dict:
        if self._is_cache_valid(site):
            cached = self._cache[site].copy()
            del cached["_cached_at"]
            return cached

        url_format = self._discover_url_format(site, homepage_html)
        self._cache[site] = url_format
        cached = url_format.copy()
        del cached["_cached_at"]
        return cached

    def build_search_url(
        self, site: str, query: str, page: int = 1, homepage_html: str = ""
    ) -> str:
        url_format = self.get_url_format(site, homepage_html)
        pattern = url_format.get("search_url_pattern", "")
        search_param = url_format.get("search_param", "q")
        page_param = url_format.get("page_param", "page")

        if "{" in pattern and "}" in pattern:
            try:
                pattern = pattern.format(query=query)
            except Exception:
                pattern = f"{pattern}?{search_param}={query}"
        else:
            sep = "?" if "?" not in pattern else "&"
            pattern = f"{pattern}{sep}{search_param}={query}"

        if page > 1 and page_param:
            sep = "&" if "?" in pattern else "?"
            pattern = f"{pattern}{sep}{page_param}={page}"

        return pattern

    def invalidate_cache(self, site: str = "") -> None:
        if site:
            self._cache.pop(site, None)
        else:
            self._cache.clear()


url_discovery = URLDiscovery()


def discover_site_url(site: str, query: str, page: int = 1, homepage_html: str = "") -> str:
    return url_discovery.build_search_url(site, query, page, homepage_html)
