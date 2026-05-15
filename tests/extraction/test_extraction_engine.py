"""ExtractionEngine 单元测试"""
import pytest
from unittest.mock import Mock
from ai_crawler.spider.extraction.engine import ExtractionEngine, ExtractionOutcomeType
from ai_crawler.spider.extraction.engine.policy_engine import ExtractionPolicyEngine
from ai_crawler.spider.extraction.analysis.page_analyzer import PageFeatures
from ai_crawler.spider.extraction.base import ExtractionResult
from ai_crawler.spider.runtime.crawl import CrawlTask, PagePattern
from ai_crawler.models.product import Product


class MockExtractor:
    def __init__(self, name, method, products=None):
        self.name = name
        self.method = method
        self._products = products or []

    def extract(self, page, html, url):
        return self._products


class MockStrategy:
    def __init__(self, name, method, products=None):
        self.name = name
        self.method = method
        self._products = products or []

    def extract(self, page, html, url):
        return self._products


class MockTemplateStore:
    def __init__(self, template=None):
        self.template = template

    def get(self, site, page_type):
        return self.template


class MockTask:
    def __init__(self):
        self.site = "test_site"
        self.page_pattern = PagePattern.SEARCH
        self.url = "https://example.com/search"


class TestExtractionEngine:
    def setup_method(self):
        self.policy_engine = ExtractionPolicyEngine()
        self.strategies = {
            "json_ld": MockStrategy("json_ld", "json_ld"),
            "bs_css": MockStrategy("bs_css", "beautifulsoup"),
            "axtree": MockStrategy("axtree", "accessibility_tree"),
        }
        self.engine = ExtractionEngine(
            strategies=self.strategies,
            policy_engine=self.policy_engine,
        )

    def test_returns_empty_when_no_extractors_match(self):
        engine = ExtractionEngine(
            strategies={},
            policy_engine=self.policy_engine,
        )
        decision = engine.extract(MockTask(), None, "<html></html>")
        assert decision.outcome == ExtractionOutcomeType.EMPTY_CONTENT
        assert decision.products == []

    def test_success_returns_products(self):
        products = [
            Product(source="test", url="p1", title="Product 1"),
            Product(source="test", url="p2", title="Product 2"),
            Product(source="test", url="p3", title="Product 3"),
        ]
        self.strategies["json_ld"] = MockStrategy("json_ld", "json_ld", products)

        decision = self.engine.extract(MockTask(), None, "<html>test</html>")

        assert decision.outcome == ExtractionOutcomeType.SUCCESS
        assert len(decision.products) == 3
        assert decision.strategy_name == "json_ld"

    def test_partial_content_when_few_products(self):
        products = [Product(source="test", url="p1", title="Product 1")]
        self.strategies["json_ld"] = MockStrategy("json_ld", "json_ld", products)

        decision = self.engine.extract(MockTask(), None, "<html>test</html>")

        assert decision.outcome == ExtractionOutcomeType.PARTIAL_CONTENT

    def test_records_result_to_policy_engine(self):
        products = [Product(source="test", url="p1", title="Product 1")]
        self.strategies["json_ld"] = MockStrategy("json_ld", "json_ld", products)

        self.engine.extract(MockTask(), None, "<html>test</html>")

        stats = self.policy_engine.get_stats("test_site", "search")
        assert stats is not None
        assert "json_ld" in stats

    def test_unknown_site_uses_default_order(self):
        order = self.policy_engine.get_order("unknown", "search", PageFeatures())
        assert order == ["json_ld", "api_intercept", "js_eval", "axtree", "bs_css"]
