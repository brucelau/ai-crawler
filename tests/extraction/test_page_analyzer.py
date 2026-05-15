"""PageAnalyzer 单元测试"""
import pytest
from ai_crawler.spider.extraction.analysis.page_analyzer import PageAnalyzer, PageFeatures


class TestPageAnalyzer:
    def setup_method(self):
        self.analyzer = PageAnalyzer()

    def test_detect_json_ld(self):
        html = '<html><script type="application/ld+json">{"@type":"Product"}</script></html>'
        features = self.analyzer.analyze(html)
        assert features.has_json_ld is True

    def test_no_json_ld(self):
        html = '<html><body><p>No structured data</p></body></html>'
        features = self.analyzer.analyze(html)
        assert features.has_json_ld is False

    def test_detect_spa_next_data(self):
        html = '<html><script>window.__NEXT_DATA__={"props":{}}</script></html>'
        features = self.analyzer.analyze(html)
        assert features.has_spa_signature is True

    def test_detect_spa_nuxt(self):
        html = '<html><script>window.__NUXT__={}</script></html>'
        features = self.analyzer.analyze(html)
        assert features.has_spa_signature is True

    def test_detect_api_signatures(self):
        html = '<html><body><p>product search item goods catalog</p></body></html>'
        features = self.analyzer.analyze(html)
        assert features.has_api_signatures is True

    def test_no_api_signatures(self):
        html = '<html><body><p>Hello world</p></body></html>'
        features = self.analyzer.analyze(html)
        assert features.has_api_signatures is False

    def test_detect_amp(self):
        html = '<html amp><body>⚡</body></html>'
        features = self.analyzer.analyze(html)
        assert features.has_amp is True

    def test_empty_html(self):
        features = self.analyzer.analyze("")
        assert features.has_json_ld is False
        assert features.has_spa_signature is False

    def test_script_ratio(self):
        html = '<html><script>long script here</script><body>content</body></html>'
        features = self.analyzer.analyze(html)
        assert features.script_ratio > 0

    def test_recommendations_json_ld(self):
        features = PageFeatures(has_json_ld=True)
        recs = self.analyzer.get_recommendations(features)
        assert "json_ld" in recs

    def test_recommendations_spa(self):
        features = PageFeatures(has_spa_signature=True)
        recs = self.analyzer.get_recommendations(features)
        assert "js_eval" in recs
        assert "axtree" in recs

    def test_recommendations_infinite_scroll(self):
        features = PageFeatures(is_infinite_scroll=True)
        recs = self.analyzer.get_recommendations(features)
        assert "js_eval" in recs

    def test_recommendations_default(self):
        features = PageFeatures()
        recs = self.analyzer.get_recommendations(features)
        assert "bs_css" in recs
