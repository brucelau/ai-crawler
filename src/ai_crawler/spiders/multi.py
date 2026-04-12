from ai_crawler.spiders.base import EcommerceSpider


class MultiSiteSpider(EcommerceSpider):
    name = "multi"

    custom_settings = {
        **EcommerceSpider.custom_settings,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    SITE_URLS = {
        "amazon": "https://www.amazon.com/s?k={query}",
        "walmart": "https://www.walmart.com/search?q={query}",
        "target": "https://www.target.com/s?searchTerm={query}",
        "ebay": "https://www.ebay.com/sch/i.html?_nkw={query}",
        "bestbuy": "https://www.bestbuy.com/site/search?search={query}",
        "lowes": "https://www.lowes.com/search?query={query}",
        "homedepot": "https://www.homedepot.com/s/{query}",
        "temu": "https://www.temu.com/search_result.html?search_key={query}",
        "etsy": "https://www.etsy.com/search?q={query}",
        "wayfair": "https://www.wayfair.com/keyword.php?keyword={query}",
        "kohls": "https://www.kohls.com/search.jsp?search={query}",
        "costco": "https://www.costco.com/s/{query}",
        "qvc": "https://www.qvc.com/forms/search-results?search={query}",
        "michaels": "https://www.michaels.com/search?search={query}",
        "acehardware": "https://www.acehardware.com/search.do?query={query}",
        "menards": "https://www.menards.com/main/search.html?query={query}",
        "samsclub": "https://www.samsclub.com/s/{query}",
        "bunnings": "https://www.bunnings.com.au/search#?q={query}",
        "mercadolibre": "https://www.mercadolibre.com.mx/busca/{query}",
        "intexcorp": "https://www.intexcorp.com/search?q={query}",
        "meijer": "https://www.meijer.com/shop/search?query={query}",
        "fivebelow": "https://www.fivebelow.com/search?q={query}",
        "dollargeneral": "https://www.dollargeneral.com/search?q={query}",
        "action": "https://www.action.com/search?q={query}",
        "academy": "https://www.academy.com/search?query={query}",
        "wowsports": "https://www.wowsports.com/search?q={query}",
        "coppel": "https://www.coppel.com/busca?q={query}",
        "aosom": "https://www.aosom.com/search?q={query}",
        "familydollar": "https://www.familydollar.com/search?q={query}",
        "costway": "https://www.costway.com/search?q={query}",
    }

    def __init__(
        self, sites: str = None, query: str = "inflatable", pages: int = 3, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.query = query
        self.pages = int(pages) if str(pages).isdigit() else int(str(pages)) if pages else 1
        self.sites = [s.strip() for s in (sites or ",".join(self.SITE_URLS.keys())).split(",")]

    async def start(self):
        for site in self.sites:
            if site not in self.SITE_URLS:
                continue
            base_url = self.SITE_URLS[site].format(query=self.query.replace(" ", "+"))
            for page in range(1, int(self.pages) + 1):
                if page > 1:
                    url = f"{base_url}&page={page}"
                else:
                    url = base_url
                yield self.make_requests_from_url(url)

    def make_requests_from_url(self, url):
        from scrapy import Request

        return Request(
            url=url,
            callback=self.parse,
            errback=self.handle_error,
        )
