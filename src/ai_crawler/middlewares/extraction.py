from scrapy import Spider
from scrapy.http import Response

from ai_crawler.core.extraction import (
    ExtractionResult,
    ExtractionStrategy,
    JSONLDExtraction,
    JSEvaluateExtraction,
    APIInterceptExtraction,
    BSExtraction,
    ExtractorChain,
    SITE_EXTRACTION_CHAINS,
)
from ai_crawler.spiders import Product


class ExtractionPipeline:
    def __init__(self):
        self._default_extractors = {}

    def _get_extractor_chain(self, site: str) -> ExtractorChain:
        return SITE_EXTRACTION_CHAINS.get(site)

    def _create_default_chain(self) -> ExtractorChain:
        return ExtractorChain(
            [
                ("json_ld", 3, JSONLDExtraction()),
                ("js_eval", 5, JSEvaluateExtraction()),
                ("bs_css", 3, BSExtraction()),
            ]
        )

    def extract(self, response: Response, page=None) -> list[Product]:
        site = self._detect_site(response.url)
        chain = self._get_extractor_chain(site)

        if not chain:
            chain = self._create_default_chain()

        result = chain.extract(page, response.text, response.url)
        return result.products

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

    def process_response(self, request, response, spider):
        if not hasattr(spider, "extract_products"):
            return response

        site = request.meta.get("site", "")
        chain = self.extraction_pipeline._get_extractor_chain(site)

        if not chain:
            return response

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
