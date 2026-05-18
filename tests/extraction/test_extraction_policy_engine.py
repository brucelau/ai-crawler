"""ExtractionPolicyEngine 单元测试"""
import pytest
from ai_crawler.extraction.policy import ExtractionPolicyEngine
from ai_crawler.extraction.analysis.page_analyzer import PageFeatures
from ai_crawler.core.types import SiteMemory


class TestExtractionPolicyEngine:
    def setup_method(self):
        self.engine = ExtractionPolicyEngine()

    def test_default_order(self):
        features = PageFeatures()
        order = self.engine.get_order("unknown_site", "search", features)
        assert order == ["json_ld", "api_intercept", "js_eval", "axtree", "bs_css"]

    def test_json_ld_boosted_when_present(self):
        features = PageFeatures(has_json_ld=True)
        order = self.engine.get_order("any_site", "search", features)
        assert order[0] == "json_ld"

    def test_spa_boosts_js_eval_and_axtree(self):
        features = PageFeatures(has_spa_signature=True)
        order = self.engine.get_order("any_site", "search", features)
        assert order.index("js_eval") < order.index("bs_css")
        assert order.index("axtree") < order.index("bs_css")

    def test_api_signatures_boosts_api_intercept(self):
        features = PageFeatures(has_api_signatures=True)
        order = self.engine.get_order("any_site", "search", features)
        assert order[0] == "api_intercept"

    def test_order_cached(self):
        features = PageFeatures()
        order1 = self.engine.get_order("site", "search", features)
        order2 = self.engine.get_order("site", "search", features)
        assert order1 == order2

    def test_record_updates_memory(self):
        self.engine.record("site", "search", "json_ld", 5, True)
        stats = self.engine.get_stats("site", "search")
        assert stats is not None
        assert "json_ld" in stats

    def test_get_best_method(self):
        self.engine.record("site", "search", "json_ld", 10, True)
        self.engine.record("site", "search", "bs_css", 5, True)
        best = self.engine.get_best_method("site", "search")
        assert best == "json_ld"

    def test_unknown_site_returns_none_for_best(self):
        best = self.engine.get_best_method("unknown", "search")
        assert best is None

    def test_unknown_site_returns_default_order(self):
        features = PageFeatures()
        order = self.engine.get_order("new_site", "search", features)
        assert order == ["json_ld", "api_intercept", "js_eval", "axtree", "bs_css"]
