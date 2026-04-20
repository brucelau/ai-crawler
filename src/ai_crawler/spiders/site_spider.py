from dataclasses import dataclass
from typing import Optional

from scrapy import Request
from scrapy.spiders import Spider

from ai_crawler.models.product import Product


@dataclass
class SiteConfig:
    name: str
    domains: list[str]
    search_url_template: str
    search_page_param: str = "page"


DEFAULT_SITES = {
    "amazon": SiteConfig(
        name="amazon",
        domains=["amazon.com", "www.amazon.com"],
        search_url_template="https://www.amazon.com/s?k={query}",
        search_page_param="page",
    ),
    "walmart": SiteConfig(
        name="walmart",
        domains=["walmart.com", "www.walmart.com"],
        search_url_template="https://www.walmart.com/search?q={query}",
        search_page_param="page",
    ),
    "target": SiteConfig(
        name="target",
        domains=["target.com", "www.target.com"],
        search_url_template="https://www.target.com/s?searchTerm={query}",
        search_page_param="page",
    ),
    "ebay": SiteConfig(
        name="ebay",
        domains=["ebay.com", "www.ebay.com"],
        search_url_template="https://www.ebay.com/sch/i.html?_nkw={query}",
        search_page_param="page",
    ),
    "bestbuy": SiteConfig(
        name="bestbuy",
        domains=["bestbuy.com", "www.bestbuy.com"],
        search_url_template="https://www.bestbuy.com/site/search?search={query}",
        search_page_param="page",
    ),
    "lowes": SiteConfig(
        name="lowes",
        domains=["lowes.com", "www.lowes.com"],
        search_url_template="https://www.lowes.com/search?searchTerm={query}",
        search_page_param="page",
    ),
    "homedepot": SiteConfig(
        name="homedepot",
        domains=["homedepot.com", "www.homedepot.com"],
        search_url_template="https://www.homedepot.com/s/?keyword={query}",
        search_page_param="page",
    ),
    "temu": SiteConfig(
        name="temu",
        domains=["temu.com", "www.temu.com"],
        search_url_template="https://www.temu.com/search?search_key={query}",
        search_page_param="page",
    ),
    "etsy": SiteConfig(
        name="etsy",
        domains=["etsy.com", "www.etsy.com"],
        search_url_template="https://www.etsy.com/search?q={query}",
        search_page_param="ref",
    ),
    "wayfair": SiteConfig(
        name="wayfair",
        domains=["wayfair.com", "www.wayfair.com"],
        search_url_template="https://www.wayfair.com/keyword.php?keyword={query}",
        search_page_param="page",
    ),
    "kohls": SiteConfig(
        name="kohls",
        domains=["kohls.com", "www.kohls.com"],
        search_url_template="https://www.kohls.com/search.jsp?search={query}",
        search_page_param="page",
    ),
    "costco": SiteConfig(
        name="costco",
        domains=["costco.com", "www.costco.com"],
        search_url_template="https://www.costco.com/search?search={query}",
        search_page_param="page",
    ),
    "qvc": SiteConfig(
        name="qvc",
        domains=["qvc.com", "www.qvc.com"],
        search_url_template="https://www.qvc.com/forms/search/results?baseCountry=us&language=en-US&search={query}",
        search_page_param="page",
    ),
    "michaels": SiteConfig(
        name="michaels",
        domains=["michaels.com", "www.michaels.com"],
        search_url_template="https://www.michaels.com/search?search={query}",
        search_page_param="page",
    ),
    "acehardware": SiteConfig(
        name="acehardware",
        domains=["acehardware.com", "www.acehardware.com"],
        search_url_template="https://www.acehardware.com/search?query={query}",
        search_page_param="page",
    ),
    "menards": SiteConfig(
        name="menards",
        domains=["menards.com", "www.menards.com"],
        search_url_template="https://www.menards.com/main/search.html?query={query}",
        search_page_param="page",
    ),
    "samsclub": SiteConfig(
        name="samsclub",
        domains=["samsclub.com", "www.samsclub.com"],
        search_url_template="https://www.samsclub.com/search?query={query}",
        search_page_param="page",
    ),
    "bunnings": SiteConfig(
        name="bunnings",
        domains=["bunnings.com.au", "www.bunnings.com.au"],
        search_url_template="https://www.bunnings.com.au/search?query={query}",
        search_page_param="page",
    ),
    "mercadolibre": SiteConfig(
        name="mercadolibre",
        domains=["mercadolibre.com.mx", "www.mercadolibre.com.mx"],
        search_url_template="https://listado.mercadolibre.com.mx/{query}",
        search_page_param="page",
    ),
    "intexcorp": SiteConfig(
        name="intexcorp",
        domains=["intexcorp.com", "www.intexcorp.com"],
        search_url_template="https://www.intexcorp.com/search?q={query}",
        search_page_param="page",
    ),
    "meijer": SiteConfig(
        name="meijer",
        domains=["meijer.com", "www.meijer.com"],
        search_url_template="https://www.meijer.com/shopping/search/{query}",
        search_page_param="page",
    ),
    "fivebelow": SiteConfig(
        name="fivebelow",
        domains=["fivebelow.com", "www.fivebelow.com"],
        search_url_template="https://www.fivebelow.com/search?q={query}",
        search_page_param="page",
    ),
    "dollargeneral": SiteConfig(
        name="dollargeneral",
        domains=["dollargeneral.com", "www.dollargeneral.com"],
        search_url_template="https://www.dollargeneral.com/search?text={query}",
        search_page_param="page",
    ),
    "action": SiteConfig(
        name="action",
        domains=["action.com", "www.action.com"],
        search_url_template="https://www.action.com/search?q={query}",
        search_page_param="page",
    ),
    "academy": SiteConfig(
        name="academy",
        domains=["academy.com", "www.academy.com"],
        search_url_template="https://www.academy.com/shop/search?q={query}",
        search_page_param="page",
    ),
    "wowsports": SiteConfig(
        name="wowsports",
        domains=["wowsports.com", "www.wowsports.com"],
        search_url_template="https://wowsports.com/search?q={query}",
        search_page_param="page",
    ),
    "coppel": SiteConfig(
        name="coppel",
        domains=["coppel.com", "www.coppel.com"],
        search_url_template="https://www.coppel.com/search?term={query}",
        search_page_param="page",
    ),
    "aosom": SiteConfig(
        name="aosom",
        domains=["aosom.com", "www.aosom.com"],
        search_url_template="https://www.aosom.com/search?q={query}",
        search_page_param="page",
    ),
    "familydollar": SiteConfig(
        name="familydollar",
        domains=["familydollar.com", "www.familydollar.com"],
        search_url_template="https://www.familydollar.com/search?q={query}",
        search_page_param="page",
    ),
    "costway": SiteConfig(
        name="costway",
        domains=["costway.com", "www.costway.com"],
        search_url_template="https://www.costway.com/search?q={query}",
        search_page_param="page",
    ),
}


class SiteSpider(Spider):
    name = "site"
    allowed_domains = []

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "COOKIES_ENABLED": True,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 3,
        "AUTOTHROTTLE_MAX_DELAY": 60,
        "DOWNLOAD_DELAY": 5,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "RETRY_TIMES": 3,
    }

    def __init__(
        self,
        site: Optional[str] = None,
        config: Optional[SiteConfig] = None,
        query: str = "inflatable",
        pages: int = 3,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        if config:
            self.site_config = config
        elif site and site in DEFAULT_SITES:
            self.site_config = DEFAULT_SITES[site]
        else:
            raise ValueError(f"Unknown site: {site or 'none'}")

        self.name = self.site_config.name
        self.allowed_domains = self.site_config.domains
        self.query = query
        self.pages = pages

    def start(self):
        base_url = self.site_config.search_url_template.format(query=self.query.replace(" ", "+"))
        for page in range(1, self.pages + 1):
            url = self._build_url(base_url, page)
            yield self.make_requests_from_url(url)

    def _build_url(self, base_url: str, page: int) -> str:
        if page == 1:
            return base_url
        sep = "&" if "?" in base_url else "?"
        return f"{base_url}{sep}{self.site_config.search_page_param}={page}"

    def make_requests_from_url(self, url: str):
        return Request(
            url=url,
            callback=self.parse,
            errback=self.handle_error,
            meta={"site": self.site_config.name, "page_type": "search"},
        )

    def parse(self, response):
        from ai_crawler.spiders.base import EcommerceSpider

        spider = EcommerceSpider()
        spider.logger = self.logger
        yield from spider.parse(response)

    def handle_error(self, failure):
        self.logger.error(f"Request failed: {failure.request.url}: {failure}")
