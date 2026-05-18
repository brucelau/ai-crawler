from ai_crawler.extraction import BSExtractor


def test_bs_extraction_ebay_search_parses_results_from_listing_cards():
    html = """
    <html><body>
      <li data-listingid="123">
        <div class="s-card__title">Office Chair Ergonomic Mesh Desk Chair</div>
        <a href="https://www.ebay.com/itm/123456?itmmeta=abc"></a>
        <div class="s-card__price">$143.99</div>
        <img src="https://example.com/chair.jpg" />
      </li>
      <li data-listingid="456">
        <div class="s-card__title">Dining Chair Set of 4</div>
        <a href="https://www.ebay.com/itm/789000?itmmeta=xyz"></a>
        <div class="s-card__price">$89.50</div>
      </li>
    </body></html>
    """

    products = BSExtractor().extract(
        html=html, page=None, url="https://www.ebay.com/sch/i.html?_nkw=chair"
    )

    assert len(products) == 2
    assert products[0].title == "Office Chair Ergonomic Mesh Desk Chair"
    assert products[0].price == "143.99"
    assert products[0].url == "https://www.ebay.com/itm/123456"
