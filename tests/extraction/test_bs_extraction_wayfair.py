from ai_crawler.spider.extraction import BSExtractor


def test_bs_extraction_wayfair_search_parses_product_cards():
    html = """
    <html><body>
      <div class="card">
        <a aria-label="Accent Chairs For Living Room" href="https://www.wayfair.com/furniture/pdp/alcott-hill-accent-chairs-for-living-room-w115254150.html?piid=1">30-Day Low Price</a>
        <a aria-label="Lemley Mid Century Solid Wood Accent Chair Upholstered Armchair with an Extra Pillow" href="https://www.wayfair.com/furniture/pdp/george-oliver-lemley-mid-century-solid-wood-accent-chair-upholstered-armchair-with-an-extra-pillow-w010279060.html?piid=2"></a>
        <img alt="Lemley Mid Century Solid Wood Accent Chair Upholstered Armchair with an Extra Pillow" src="https://example.com/chair.jpg" />
        <div>$239.99</div>
      </div>
      <div class="card">
        <a aria-label="Braedin Upholstered Accent Chair &amp; Storable Ottoman, No Assembly Required" href="https://www.wayfair.com/furniture/pdp/wade-logan-braedin-upholstered-accent-chair-storable-ottoman-no-assembly-required-cfam1341.html?piid=3">Tax Refund Sale</a>
        <a aria-label="Braedin Upholstered Accent Chair &amp; Storable Ottoman, No Assembly Required" href="https://www.wayfair.com/furniture/pdp/wade-logan-braedin-upholstered-accent-chair-storable-ottoman-no-assembly-required-cfam1341.html?piid=3"></a>
        <div>$189.50</div>
      </div>
    </body></html>
    """

    products = BSExtractor().extract(
        html=html, page=None, url="https://www.wayfair.com/keyword.php?keyword=chair"
    )

    assert len(products) == 2
    assert products[0].title.startswith("Lemley Mid Century")
    assert products[0].price == "239.99"
    assert products[1].title.startswith("Braedin Upholstered Accent Chair")
