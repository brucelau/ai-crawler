from ai_crawler.core.engine.extraction_runtime import ExtractionRuntimeService
from ai_crawler.core.strategy import CrawlStrategy, CrawlTask, PagePattern, RenderType
from ai_crawler.models.product import Product


def test_extraction_runtime_uses_template_then_universal_extractor(monkeypatch):
    from ai_crawler.core.extraction.template_based import (
        save_template,
        ExtractionTemplate,
        clear_templates,
    )

    clear_templates()
    save_template(
        ExtractionTemplate(
            site="amazon",
            page_type="search",
            css_selector="li.product",
        )
    )

    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )
    service = ExtractionRuntimeService({})

    monkeypatch.setattr(
        "ai_crawler.core.llm.llm_extractor.extract_with_llm_page",
        lambda html, page, site, page_type, url, force_regenerate=False: [],
    )

    decision = service.extract(
        task, CrawlStrategy(render=RenderType.CLOUDERA), None, "<html></html>"
    )

    assert decision.should_retry is True
    assert decision.retry_reason == "empty_content"

    clear_templates()


def test_extraction_runtime_still_retries_when_no_products_and_no_llm_fallback(monkeypatch):
    class EmptyChain:
        def extract(self, page, html, url, page_type="unknown"):
            from ai_crawler.core.extraction import ExtractionResult

            return ExtractionResult(products=[], strategy="bs_css", method="css")

    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )
    service = ExtractionRuntimeService({"amazon": EmptyChain()})

    monkeypatch.setattr(
        "ai_crawler.core.llm.llm_extractor.extract_with_llm_page",
        lambda html, page, site, page_type, url, force_regenerate=False: [],
    )

    decision = service.extract(
        task, CrawlStrategy(render=RenderType.PLAYWRIGHT), object(), "<html></html>"
    )

    assert decision.should_retry is True
    assert decision.retry_reason == "empty_content"


def test_extraction_runtime_generates_template_after_universal_success(monkeypatch):
    from ai_crawler.core.extraction.template_based import (
        save_template,
        ExtractionTemplate,
        get_template,
        clear_templates,
    )

    clear_templates()

    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )
    service = ExtractionRuntimeService({})

    template_saved = []

    def fake_llm_generate(site, page_type, html, products, page=None):
        template_saved.append(True)
        return ExtractionTemplate(
            site=site,
            page_type=page_type,
            css_selector="li.product",
        )

    monkeypatch.setattr(
        "ai_crawler.core.extraction.template_based.llm_generate_template",
        fake_llm_generate,
    )

    fake_result = type("R", (), {
        "products": [Product(source="amazon", url="https://amazon.com/s?k=chair", title="Chair")],
        "strategy": "json_ld",
        "method": "json_ld"
    })()

    monkeypatch.setattr(
        "ai_crawler.core.extraction.template_based.UniversalExtractor.extract",
        lambda self, page, html, url, page_type, intercepted_products=None: fake_result,
    )

    decision = service.extract(
        task, CrawlStrategy(render=RenderType.CLOUDERA), object(), "<html></html>"
    )

    assert decision.should_retry is False
    assert len(decision.products) == 1
    assert decision.strategy_name == "json_ld"

    clear_templates()


def test_extraction_runtime_retries_after_uc_success_without_products(monkeypatch):
    class EmptyChain:
        def extract(self, page, html, url, page_type="unknown"):
            from ai_crawler.core.extraction import ExtractionResult

            return ExtractionResult(products=[], strategy="none", method="none")

    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )
    service = ExtractionRuntimeService({"amazon": EmptyChain()})

    monkeypatch.setattr(
        "ai_crawler.core.llm.llm_extractor.extract_with_llm_page",
        lambda html, page, site, page_type, url, force_regenerate=False: [],
    )

    decision = service.extract(
        task, CrawlStrategy(render=RenderType.CLOUDERA), None, "<html></html>"
    )

    assert decision.should_retry is True
    assert decision.retry_reason == "empty_content"
