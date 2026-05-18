from ai_crawler.extraction import BSExtractor


def test_bs_extraction_target_search_parses_product_links():
    html = """
    <html><body>
      <div class="card">
        <a href="/p/patio-chair/-/A-123" aria-label="Outdoor Patio Chair">
          <img src="https://example.com/chair.jpg" />
        </a>
        <span>$143.98</span>
      </div>
      <div class="card">
        <a href="/p/barrel-chair/-/A-456">Barrel Chair with Storage Ottoman Set</a>
        <span>$89.99</span>
      </div>
    </body></html>
    """

    products = BSExtractor().extract(
        html=html, page=None, url="https://www.target.com/s?searchTerm=chair"
    )

    assert len(products) == 2
    assert products[0].title == "Outdoor Patio Chair"
    assert products[0].price == "143.98"
    assert products[0].url == "https://www.target.com/p/patio-chair/-/A-123"
