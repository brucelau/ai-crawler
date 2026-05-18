from ai_crawler.extraction import (
    AXTreeExtractor,
    build_axtree_selector_sample,
)


def test_axtree_extraction_returns_empty_without_page():
    extractor = AXTreeExtractor()

    assert extractor.extract(None, "<html></html>", "https://www.amazon.com/s?k=chair") == []


def test_axtree_extraction_parses_products_from_cdp_tree():
    extractor = AXTreeExtractor()

    class FakeSession:
        def send(self, method):
            assert method == "Accessibility.getFullAXTree"
            return {
                "nodes": [
                    {
                        "nodeId": "1",
                        "role": {"value": "listitem"},
                        "name": {"value": "Outdoor Chair Deluxe"},
                        "description": {"value": "$19.99"},
                    },
                    {
                        "nodeId": "2",
                        "role": {"value": "listitem"},
                        "name": {"value": "Pool Lounger"},
                        "description": {"value": "$29.99 120 reviews 4.8 stars"},
                    },
                    {
                        "nodeId": "3",
                        "role": {"value": "listitem"},
                        "name": {"value": "Patio Seat"},
                        "description": {"value": "$39.99"},
                    },
                ]
            }

        def detach(self):
            return None

    class FakeContext:
        def new_cdp_session(self, page):
            return FakeSession()

    class FakePage:
        context = FakeContext()

    products = extractor.extract(FakePage(), "<html></html>", "https://www.amazon.com/s?k=chair")

    assert len(products) == 3
    assert products[0].title == "Outdoor Chair Deluxe"
    assert products[0].price == "$19.99"
    assert products[1].review_count == 120
    assert products[1].rating == 4.8


def test_axtree_extraction_ignores_site_specific_noise_in_titles():
    extractor = AXTreeExtractor()

    payload = {
        "nodes": [
            {
                "role": "listitem",
                "name": "Sponsored",
                "description": "$18.99",
                "children": [],
                "path": "1",
            },
            {
                "role": "listitem",
                "name": "Premium Patio Chair",
                "description": "$48.99 200 reviews 4.7 stars",
                "children": [],
                "path": "2",
            },
        ]
    }

    products = extractor._products_from_payload(payload, "https://www.amazon.com/s?k=chair")

    assert len(products) == 1
    assert products[0].title == "Premium Patio Chair"


def test_build_axtree_selector_sample_summarizes_visible_products():
    class FakeSession:
        def send(self, method):
            assert method == "Accessibility.getFullAXTree"
            return {
                "nodes": [
                    {
                        "nodeId": "1",
                        "role": {"value": "listitem"},
                        "name": {"value": "Outdoor Chair Deluxe"},
                        "description": {"value": "$19.99"},
                    },
                    {
                        "nodeId": "2",
                        "role": {"value": "listitem"},
                        "name": {"value": "Pool Lounger"},
                        "description": {"value": "$29.99 120 reviews 4.8 stars"},
                    },
                ]
            }

        def detach(self):
            return None

    class FakeContext:
        def new_cdp_session(self, page):
            return FakeSession()

    class FakePage:
        context = FakeContext()

    sample = build_axtree_selector_sample(
        FakePage(),
        "https://www.amazon.com/s?k=chair",
        page_pattern="search",
    )

    assert "semantic_kind=search" in sample
    assert "visible_product_candidates:" in sample
    assert "Outdoor Chair Deluxe" in sample
