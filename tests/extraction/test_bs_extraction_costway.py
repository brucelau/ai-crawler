from ai_crawler.extraction import BSExtractor


def test_bs_extraction_costway_search_parses_product_items():
    html = """
    <html><body>
      <div class="product-item">
        <div class="product-images">
          <a href="/2-25hp-2-in-1-folding-treadmill-with-bluetooth-speaker-remote-control.html">
            <img alt="2.25HP 2 in 1 Folding Treadmill with APP Speaker Remote Control" src="https://example.com/treadmill.jpg" />
          </a>
        </div>
        <div class="price">$1,095</div>
      </div>
      <div class="product-item">
        <div class="product-images">
          <a href="/barrel-chair-accent-chair-set.html">
            <img alt="Barrel Accent Chair Set" src="https://example.com/chair.jpg" />
          </a>
        </div>
        <div class="price">$258.00</div>
      </div>
    </body></html>
    """

    products = BSExtractor().extract(
        html=html, page=None, url="https://www.costway.com/search?q=chair"
    )

    assert len(products) == 2
    assert products[0].title == "2.25HP 2 in 1 Folding Treadmill with APP Speaker Remote Control"
    assert products[0].price == "1095"
    assert (
        products[0].url
        == "https://www.costway.com/2-25hp-2-in-1-folding-treadmill-with-bluetooth-speaker-remote-control.html"
    )
