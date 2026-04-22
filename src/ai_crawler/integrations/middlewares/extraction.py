from scrapy import Spider
from scrapy.http import Response

from ai_crawler.core.extraction import (
    ExtractionEngine,
    ExtractionPolicyEngine,
    STRATEGY_REGISTRY,
    create_strategy,
    TemplateStore,
    PageAnalyzer,
)
from ai_crawler.core.types import CrawlTask, PagePattern
from ai_crawler.models.product import Product


class ExtractionPipeline:
    def __init__(self):
        self._policy_engine = ExtractionPolicyEngine()
        self._strategies = {name: create_strategy(name) for name in STRATEGY_REGISTRY}
        self._template_store = TemplateStore()
        self._engine = ExtractionEngine(
            strategies=self._strategies,
            policy_engine=self._policy_engine,
            template_store=self._template_store,
        )
        self._analyzer = PageAnalyzer()

    def extract(self, response: Response, page=None, site: str = "") -> list[Product]:
        site = site or self._detect_site(response.url)
        page_type = "unknown"
        features = self._analyzer.analyze(response.text, page)
        if features.has_spa_signature:
            page_type = "search"

        task = CrawlTask.create_from_tier(
            url=response.url,
            site=site,
            page_pattern=PagePattern.SEARCH if page_type == "search" else PagePattern.UNKNOWN,
        )
        decision = self._engine.extract(task, page, response.text)
        return decision.products

    def _detect_site(self, url: str) -> str:
        if "amazon." in url:
            return "amazon"
        if "walmart." in url:
            return "walmart"
        if "target." in url:
            return "target"
        if "ebay." in url:
            return "ebay"
        if "lowes." in url:
            return "lowes"
        if "homedepot." in url:
            return "homedepot"
        if "bestbuy." in url:
            return "bestbuy"
        if "costco." in url:
            return "costco"
        if "wayfair." in url:
            return "wayfair"
        if "temu." in url:
            return "temu"
        if "etsy." in url:
            return "etsy"
        if "michaels." in url:
            return "michaels"
        if "acehardware." in url:
            return "acehardware"
        return ""


class JSExtractionMiddleware:
    def __init__(self):
        self.extraction_pipeline = ExtractionPipeline()

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def process_response(self, request, response):
        strategy = request.meta.get("current_strategy")
        if strategy and strategy.render.value in (
            "camoufox",
            "cloakbrowser",
            "playwright",
            "seleniumbase",
        ):
            request.meta["use_js_extraction"] = True
        return response

    def process_item(self, item, spider):
        return item
