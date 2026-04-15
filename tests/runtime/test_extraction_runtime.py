from ai_crawler.core.runtime.extraction_runtime import ExtractionRuntimeService
from ai_crawler.core.strategy import CrawlStrategy, CrawlTask, PagePattern, RenderType
from ai_crawler.models.product import Product


def test_extraction_runtime_uses_llm_fallback_when_chain_returns_no_products(monkeypatch):
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
        lambda html, page, site, page_type, url: [Product(source=site, url=url, title="Chair")],
    )

    decision = service.extract(
        task, CrawlStrategy(render=RenderType.CLOUDERA), None, "<html></html>"
    )

    assert decision.should_retry is False
    assert len(decision.products) == 1
    assert decision.strategy_name == "llm_selector_fallback"


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


def test_extraction_runtime_forces_llm_regeneration_after_empty_fallback(monkeypatch):
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

    calls = []

    def fake_llm(html, page, site, page_type, url, force_regenerate=False):
        calls.append(force_regenerate)
        if force_regenerate:
            return [Product(source=site, url=url, title="Chair")]
        return []

    monkeypatch.setattr("ai_crawler.core.llm.llm_extractor.extract_with_llm_page", fake_llm)

    decision = service.extract(
        task, CrawlStrategy(render=RenderType.CLOUDERA), None, "<html></html>"
    )

    assert calls == [False, True]
    assert decision.should_retry is False
    assert len(decision.products) == 1


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
