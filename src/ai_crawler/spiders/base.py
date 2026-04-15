from scrapy import Spider, Item, Field
from scrapy.http import Response
from ai_crawler.models.product import Product


class EcommerceItem(Item):
    source = Field()
    url = Field()
    title = Field()
    price = Field()
    currency = Field()
    rating = Field()
    review_count = Field()
    brand = Field()
    description = Field()
    images = Field()
    availability = Field()
    asin = Field()
    seller = Field()
    shipping = Field()
    category = Field()
    extracted_at = Field()


def product_to_item(product) -> EcommerceItem:
    data = product.to_dict()
    item = EcommerceItem()
    for key, value in data.items():
        item[key] = value
    return item


class EcommerceSpider(Spider):
    name = "ecommerce"
    allowed_domains = []

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "COOKIES_ENABLED": True,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 3,
        "AUTOTHROTTLE_MAX_DELAY": 60,
        "DOWNLOAD_DELAY": 5,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "RETRY_TIMES": 3,
    }

    SITE_DOMAINS = {
        "amazon": ["amazon.com", "amazon.co.uk", "amazon.de"],
        "walmart": ["walmart.com"],
        "target": ["target.com"],
        "ebay": ["ebay.com"],
        "bestbuy": ["bestbuy.com"],
        "lowes": ["lowes.com"],
        "homedepot": ["homedepot.com"],
        "temu": ["temu.com"],
        "etsy": ["etsy.com"],
        "wayfair": ["wayfair.com"],
        "kohls": ["kohls.com"],
        "costco": ["costco.com"],
        "qvc": ["qvc.com"],
        "michaels": ["michaels.com"],
        "acehardware": ["acehardware.com"],
        "menards": ["menards.com"],
        "samsclub": ["samsclub.com"],
        "bunnings": ["bunnings.com.au"],
        "mercadolibre": ["mercadolibre.com", "mercadolivre.com"],
        "intexcorp": ["intexcorp.com"],
        "meijer": ["meijer.com"],
        "fivebelow": ["fivebelow.com"],
        "dollargeneral": ["dollargeneral.com"],
        "action": ["action.com"],
        "academy": ["academy.com"],
        "wowsports": ["wowsports.com"],
        "coppel": ["coppel.com"],
        "aosom": ["aosom.com"],
        "familydollar": ["familydollar.com"],
        "costway": ["costway.com"],
    }

    def _detect_site(self, url: str):
        url_lower = url.lower()
        for site, domains in self.SITE_DOMAINS.items():
            for domain in domains:
                if domain in url_lower:
                    return site
        return None

    def _detect_page_type(self, url: str):
        import re

        url_lower = url.lower()
        detail_patterns = [r"/dp/", r"/ip/", r"/p/", r"/product/", r"/item/", r"/-/", r"/pd/"]
        for pattern in detail_patterns:
            if re.search(pattern, url_lower):
                return "detail"
        search_patterns = [
            r"/s\?",
            r"/search",
            r"/browse",
            r"/s\.",
            r"searchterm=",
            r"\?q=",
            r"_nkw=",
        ]
        for pattern in search_patterns:
            if re.search(pattern, url_lower):
                return "search"
        return "search"

    def _extract_with_llm(self, response: Response, site: str, page_type: str):
        from ai_crawler.core.llm.llm_extractor import llm_extractor

        try:
            page = None
            try:
                page = response.meta.get("page") or response.meta.get("playwright_page")
            except Exception:
                page = None
            return llm_extractor.extract_with_page(
                response.text, page, site, page_type, response.url
            )
        except Exception as e:
            self.logger.warning(f"LLM extraction failed: {e}")
            return []

    def parse(self, response: Response):
        site = self._detect_site(response.url)
        if not site:
            self.logger.warning(f"Unknown site for URL: {response.url}")
            return
        page_type = self._detect_page_type(response.url)
        if page_type == "detail":
            yield from self._parse_detail(response, site, page_type)
        else:
            yield from self._parse_list(response, site, page_type)

    def _parse_detail(self, response: Response, site: str, page_type: str):
        try:
            products = self._extract_with_llm(response, site, page_type)
            for product in products:
                yield product_to_item(product)
        except Exception as e:
            self.logger.error(f"Detail parse error: {e}", url=response.url)

    def _parse_list(self, response: Response, site: str, page_type: str):
        try:
            products = self._extract_with_llm(response, site, page_type)
            for product in products:
                yield product_to_item(product)
        except Exception as e:
            self.logger.error(f"List parse error: {e}", url=response.url)

    def handle_error(self, failure):
        self.logger.error(f"Request failed: {failure.request.url}: {failure}")
