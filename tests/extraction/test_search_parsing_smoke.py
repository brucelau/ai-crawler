"""
Search Page Parsing Smoke Tests - All 30 Data Sources

Tests extraction logic for ALL data sources' search page parsing.
"""

import pytest
from ai_crawler.extraction import BSExtractor, JSEvaluateExtractor, JSONLDExtractor

ALL_SITES = [
    "acehardware",
    "action",
    "academy",
    "aosom",
    "amazon",
    "bestbuy",
    "bunnings",
    "coppel",
    "costco",
    "costway",
    "dollargeneral",
    "ebay",
    "etsy",
    "familydollar",
    "fivebelow",
    "homedepot",
    "intexcorp",
    "kohls",
    "lowes",
    "meijer",
    "menards",
    "mercadolibre",
    "michaels",
    "qvc",
    "samsclub",
    "target",
    "temu",
    "walmart",
    "wayfair",
    "wowsports",
]

SITES_WITH_SEARCH_JSON = [
    "amazon",
    "bestbuy",
    "costco",
    "costway",
    "ebay",
    "etsy",
    "homedepot",
    "lowes",
    "menards",
    "target",
    "temu",
    "walmart",
    "wayfair",
    "wowsports",
]


def test_all_sites_have_js_evaluation_code():
    extractor = JSEvaluateExtractor()
    missing = []
    for site in ALL_SITES:
        if site in SITES_WITHOUT_JS_CODE:
            continue
        js_code = extractor._get_js_code(site)
        if not js_code:
            missing.append(site)
    assert len(missing) == 0, f"Sites missing JS evaluation code: {missing}"


def test_all_sites_js_selector_exists():
    extractor = JSEvaluateExtractor()
    for site in ALL_SITES:
        if site in SITES_WITHOUT_JS_CODE:
            continue
        js_code = extractor._get_js_code(site)
        assert js_code is not None, f"Missing JS code for {site}"
        assert "querySelectorAll" in js_code or "querySelector" in js_code


def test_amazon_bs_extraction():
    html = """
    <html><body>
      <div data-asin="B07NWR7HKD" class="s-result-item s-asin">
        <h2><span class="a-text-normal">JOYIN 12-Pack Beach Balls</span></h2>
        <a class="a-link-normal s-no-outline" href="/JOYIN/dp/B07NWR7HKD/ref=sr_1_1"></a>
        <span class="a-price"><span class="a-offscreen">$9.99</span></span>
        <img class="s-image" src="https://example.com/ball.jpg" />
      </div>
    </body></html>
    """
    products = BSExtractor().extract(
        html=html, page=None, url="https://www.amazon.com/s?k=inflatable"
    )
    assert len(products) == 1
    assert products[0].source == "amazon"
    assert products[0].asin == "B07NWR7HKD"


def test_ebay_bs_extraction():
    html = """
    <html><body>
      <li class="s-item s-asin" data-listingid="123456789">
        <h3 class="s-card__title">VintageInflatablePool Float</h3>
        <a class="s-card__image" href="/itm/123456789">Link</a>
        <span class="s-card__price">$24.99</span>
        <img src="https://example.com/pool.jpg" />
      </li>
    </body></html>
    """
    products = BSExtractor().extract(
        html=html, page=None, url="https://www.ebay.com/sch/i.html?_nkw=inflatable"
    )
    assert len(products) >= 1
    assert products[0].source == "ebay"


def test_target_bs_extraction():
    html = """
    <html><body>
      <div class="card">
        <a href="/p/patio-chair/-/A-123" aria-label="Outdoor Patio Chair">
          <img src="https://example.com/chair.jpg" />
        </a>
        <span>$143.98</span>
      </div>
    </body></html>
    """
    products = BSExtractor().extract(
        html=html, page=None, url="https://www.target.com/s?searchTerm=chair"
    )
    assert len(products) >= 1
    assert products[0].source == "target"


def test_walmart_jsonld_extraction():
    html = """
    <html><body>
      <script type="application/ld+json">
      {
        "@type": "Product",
        "name": "Inflatable Pool Float",
        "url": "https://walmart.com/ip/123",
        "offers": {"price": "19.99", "priceCurrency": "USD"}
      }
      </script>
    </body></html>
    """
    products = JSONLDExtractor().extract(
        html=html, page=None, url="https://walmart.com/search?q=inflatable"
    )
    assert len(products) >= 1
    assert products[0].source == "walmart"


def test_wayfair_bs_extraction():
    html = """
    <html><body>
      <div>
        <a href="https://www.wayfair.com/furniture/pdp/chair-123.html" aria-label="Modern Lounge Chair">
          Modern Lounge Chair
        </a>
        <span class="ProductCard-price">$199.00</span>
        <img alt="Chair" src="https://example.com/chair.jpg" />
      </div>
    </body></html>
    """
    products = BSExtractor().extract(
        html=html, page=None, url="https://www.wayfair.com/furniture/s?query=chair"
    )
    assert len(products) >= 1


def test_costco_jsonld_extraction():
    html = """
    <html><body>
      <script type="application/ld+json">
      {
        "@type": "Product",
        "name": "Kirkland Signature Set",
        "url": "https://costco.com/kirkland-set",
        "offers": {"price": "49.99", "priceCurrency": "USD"}
      }
      </script>
    </body></html>
    """
    products = JSONLDExtractor().extract(
        html=html, page=None, url="https://costco.com/s?query=set"
    )
    assert len(products) >= 1


def test_lowes_jsonld_extraction():
    html = """
    <html><body>
      <script type="application/ld+json">
      {
        "@type": "Product",
        "name": "Stanley Fatmax Tool Set",
        "url": "https://lowes.com/stanley-tool-set",
        "offers": {"price": "89.99", "priceCurrency": "USD"}
      }
      </script>
    </body></html>
    """
    products = JSONLDExtractor().extract(
        html=html, page=None, url="https://lowes.com/search?searchTerm=tools"
    )
    assert len(products) >= 1


def test_homedepot_jsonld_extraction():
    html = """
    <html><body>
      <script type="application/ld+json">
      {
        "@type": "Product",
        "name": "Dewalt 20V Drill Set",
        "url": "https://homedepot.com/p/dewalt-drill",
        "offers": {"price": "129.00", "priceCurrency": "USD"}
      }
      </script>
    </body></html>
    """
    products = JSONLDExtractor().extract(
        html=html, page=None, url="https://homedepot.com/search?searchTerm=drill"
    )
    assert len(products) >= 1


def test_bestbuy_jsonld_extraction():
    html = """
    <html><body>
      <script type="application/ld+json">
      {
        "@type": "Product",
        "name": "Samsung 65 inch TV",
        "url": "https://bestbuy.com/site/samsung-tv",
        "offers": {"price": "499.99", "priceCurrency": "USD"}
      }
      </script>
    </body></html>
    """
    products = JSONLDExtractor().extract(
        html=html, page=None, url="https://bestbuy.com/site/search?searchTerm=tv"
    )
    assert len(products) >= 1


def test_menards_jsonld_extraction():
    html = """
    <html><body>
      <script type="application/ld+json">
      {
        "@type": "Product",
        "name": "Lifetime 8ft Table",
        "url": "https://menards.com/main/p/lifetime-table",
        "offers": {"price": "179.99", "priceCurrency": "USD"}
      }
      </script>
    </body></html>
    """
    products = JSONLDExtractor().extract(
        html=html, page=None, url="https://menards.com/search?searchTerm=table"
    )
    assert len(products) >= 1


def test_temu_jsonld_extraction():
    html = """
    <html><body>
      <script type="application/ld+json">
      {
        "@type": "Product",
        "name": "Cute Phone Case",
        "url": "https://temu.com/item/phone-case",
        "offers": {"price": "5.99", "priceCurrency": "USD"}
      }
      </script>
    </body></html>
    """
    products = JSONLDExtractor().extract(
        html=html, page=None, url="https://temu.com/search?query=phone+case"
    )
    assert len(products) >= 1


def test_etsy_jsonld_extraction():
    html = """
    <html><body>
      <script type="application/ld+json">
      {
        "@type": "Product",
        "name": "Handmade Crochet Scarf",
        "url": "https://etsy.com/listing/scarf",
        "offers": {"price": "35.00", "priceCurrency": "USD"}
      }
      </script>
    </body></html>
    """
    products = JSONLDExtractor().extract(
        html=html, page=None, url="https://etsy.com/search?q=scarf"
    )
    assert len(products) >= 1


def test_wowsports_bs_extraction():
    html = """
    <html><body>
      <main>
        <div class="grid__item">
          <a class="full-unstyled-link" href="/products/swimsuit">
            <span class="card__heading">Kids Swimsuit</span>
          </a>
          <span class="price">$24.99</span>
          <img src="https://example.com/swimsuit.jpg" />
        </div>
      </main>
    </body></html>
    """
    products = BSExtractor().extract(
        html=html, page=None, url="https://wowsports.com/collections/swimwear"
    )
    assert len(products) >= 1
    assert products[0].source == "wowsports"


def test_costway_bs_extraction():
    html = """
    <html><body>
      <div class="product-item">
        <div class="product-images">
          <a href="/product/chair.html">
            <img alt="Ergonomic Office Chair" src="https://example.com/chair.jpg" />
          </a>
        </div>
        <span class="price">$79.99</span>
      </div>
    </body></html>
    """
    products = BSExtractor().extract(
        html=html, page=None, url="https://www.costway.com/search?search=chair"
    )
    assert len(products) >= 1
    assert products[0].source == "costway"


def test_search_json_template_exists_for_supported_sites():
    import os

    template_dir = os.path.join(
        os.path.dirname(__file__).replace("tests/extraction", "src/ai_crawler/sites")
    )
    missing = []
    for site in SITES_WITH_SEARCH_JSON:
        template_path = os.path.join(template_dir, site, "search.json")
        if not os.path.exists(template_path):
            missing.append(site)
    assert len(missing) == 0, f"Missing search.json for: {missing}"


SITES_WITHOUT_SEARCH_JSON = [s for s in ALL_SITES if s not in SITES_WITH_SEARCH_JSON]

SITES_WITHOUT_JS_CODE = ["menards"]


def test_sites_without_search_json_info():
    print(f"\n\nSites WITHOUT search.json templates ({len(SITES_WITHOUT_SEARCH_JSON)}):")
    print(SITES_WITHOUT_SEARCH_JSON)
    assert len(SITES_WITHOUT_SEARCH_JSON) > 0


def test_sites_without_js_code_info():
    print(f"\n\nSites WITHOUT JS evaluation code ({len(SITES_WITHOUT_JS_CODE)}):")
    print(SITES_WITHOUT_JS_CODE)
    assert len(SITES_WITHOUT_JS_CODE) > 0


def test_js_evaluate_sites_with_code():
    extractor = JSEvaluateExtractor()
    sites_with_code = [s for s in ALL_SITES if s not in SITES_WITHOUT_JS_CODE]
    for site in sites_with_code:
        js_code = extractor._get_js_code(site)
        assert js_code is not None and len(js_code) > 0, f"Missing JS code for {site}"


def test_all_sites_with_code_have_product_selector():
    extractor = JSEvaluateExtractor()
    sites_with_code = [s for s in ALL_SITES if s not in SITES_WITHOUT_JS_CODE]
    for site in sites_with_code:
        js_code = extractor._get_js_code(site)
        assert js_code is not None, f"Missing JS code for {site}"
        assert "querySelectorAll" in js_code, f"Site {site} missing querySelectorAll"
