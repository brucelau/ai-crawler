from ai_crawler.spiders.base import EcommerceSpider


class FivebelowSpider(EcommerceSpider):
    name = "fivebelow"
    allowed_domains = ["fivebelow.com", "www.fivebelow.com"]

    custom_settings = {
        **EcommerceSpider.custom_settings,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    def __init__(self, query: str = "inflatable", pages: int = 3, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.query = query
        self.pages = pages

    async def start(self):
        base_url = f"https://www.fivebelow.com/search?q={self.query.replace(' ', '+')}"
        for page in range(1, self.pages + 1):
            url = f"{base_url}&page={page}" if page > 1 else base_url
            yield self.make_requests_from_url(url)

    def make_requests_from_url(self, url):
        from scrapy import Request

        return Request(
            url=url,
            callback=self.parse,
            errback=self.handle_error,
            meta={"site": "fivebelow", "page_type": "search"},
        )
