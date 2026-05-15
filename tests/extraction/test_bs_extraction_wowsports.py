from ai_crawler.spider.extraction import BSExtractor


def test_bs_extraction_wowsports_search_parses_product_cards():
    html = """
    <html><body>
      <main>
        <div class="grid__item">
          <a class="full-unstyled-link" href="/products/the-contemporary-recliner-float?_pos=1">The Contemporary Recliner Float</a>
          <h3 class="card__heading">The Contemporary Recliner Float</h3>
          <div class="price">Regular price $159.99 USD</div>
          <img src="https://example.com/float.jpg" />
        </div>
        <div class="grid__item">
          <a class="full-unstyled-link" href="/products/chaise-lounge-sun-geo?_pos=2">Chaise Lounge- Sun Geo</a>
          <h3 class="card__heading">Chaise Lounge- Sun Geo</h3>
          <div class="price">Regular price $89.99 USD</div>
        </div>
      </main>
    </body></html>
    """

    products = BSExtractor().extract(
        html=html, page=None, url="https://wowsports.com/search?q=chair"
    )

    assert len(products) == 2
    assert products[0].title == "The Contemporary Recliner Float"
    assert products[0].price == "159.99"
    assert products[0].url == "https://wowsports.com/products/the-contemporary-recliner-float"
