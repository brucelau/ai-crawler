from ai_crawler.spiders.base import EcommerceSpider


class AmazonSearchSpider(EcommerceSpider):
    name = "amazon_search"
    allowed_domains = ["amazon.com", "www.amazon.com"]

    custom_settings = {
        **EcommerceSpider.custom_settings,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    def __init__(self, query: str = "inflatable", pages: int = 3, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.query = query
        self.pages = pages

    async def start(self):
        base_url = f"https://www.amazon.com/s?k={self.query.replace(' ', '+')}"
        for page in range(1, self.pages + 1):
            url = f"{base_url}&page={page}" if page > 1 else base_url
            yield self.make_requests_from_url(url)

    def make_requests_from_url(self, url):
        from scrapy import Request

        return Request(
            url=url,
            callback=self.parse,
            errback=self.handle_error,
            meta={"site": "amazon", "page_type": "search"},
        )


class AmazonDetailSpider(EcommerceSpider):
    name = "amazon_detail"
    allowed_domains = ["amazon.com", "www.amazon.com"]

    def __init__(self, asin: str = None, url: str = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.asin = asin
        self.start_url = url or (f"https://www.amazon.com/dp/{asin}" if asin else None)

    async def start(self):
        if self.start_url:
            yield self.make_requests_from_url(self.start_url)

    def make_requests_from_url(self, url):
        from scrapy import Request

        return Request(
            url=url,
            callback=self.parse,
            errback=self.handle_error,
            meta={"site": "amazon", "page_type": "detail"},
        )
