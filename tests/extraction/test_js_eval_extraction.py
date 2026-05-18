from ai_crawler.extraction import JSEvaluateExtractor


def test_js_evaluate_extraction_returns_product_objects():
    class FakePage:
        def evaluate(self, js_code):
            return [
                {
                    "title": "Outdoor Patio Chair",
                    "price": "143.98",
                    "url": "https://www.target.com/p/patio-chair/-/A-123",
                    "image": "https://example.com/image.jpg",
                }
            ]

    products = JSEvaluateExtractor().extract(
        FakePage(),
        "<html></html>",
        "https://www.target.com/s?searchTerm=chair",
    )

    assert len(products) == 1
    assert products[0].title == "Outdoor Patio Chair"
    assert products[0].price == "143.98"
    assert products[0].url == "https://www.target.com/p/patio-chair/-/A-123"


def test_js_evaluate_extraction_infers_wowsports_and_costway_sources():
    extractor = JSEvaluateExtractor()

    assert extractor._infer_source("https://wowsports.com/search?q=chair") == "wowsports"
    assert extractor._infer_source("https://www.costway.com/search?q=chair") == "costway"
