from ai_crawler.spider.extraction import BSExtractor


def test_bs_extraction_amazon_search_parses_results_from_data_asin():
    html = """
    <html><body>
      <div data-asin="B07NWR7HKD" class="s-result-item s-asin">
        <h2><span>JOYIN 12-Pack Beach Balls</span></h2>
        <a class="a-link-normal s-no-outline" href="/JOYIN-Rainbow-Beach-Balls-Inflatable/dp/B07NWR7HKD/ref=sr_1_1"></a>
        <span class="a-price"><span class="a-offscreen">$9.99</span></span>
        <img class="s-image" src="https://example.com/ball.jpg" />
      </div>
      <div data-asin="0762462876" class="s-result-item s-asin">
        <span data-cy="title-recipe">Wacky Waving Inflatable Tube Guy</span>
        <a href="/Wacky-Waving-Inflatable-Miniature-Editions/dp/0762462876/ref=sr_1_2"></a>
        <span class="a-price"><span class="a-offscreen">$11.66</span></span>
      </div>
    </body></html>
    """

    products = BSExtractor().extract(
        html=html, page=None, url="https://www.amazon.com/s?k=inflatable"
    )

    assert len(products) == 2
    assert products[0].asin == "B07NWR7HKD"
    assert products[0].title == "JOYIN 12-Pack Beach Balls"
    assert products[0].price == "9.99"
    assert (
        products[0].url
        == "https://www.amazon.com/JOYIN-Rainbow-Beach-Balls-Inflatable/dp/B07NWR7HKD/ref=sr_1_1"
    )
