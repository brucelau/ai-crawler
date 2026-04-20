import structlog
from ai_crawler.orchestration import RuntimeOptions, RuntimeTask, SmartCrawlerRuntime
from ai_crawler.orchestration.storage import ProductOutputWriter
from ai_crawler.models.product import Product

log = structlog.get_logger()


class CrawlerConfig:
    def __init__(
        self,
        thordata_username: str,
        thordata_password: str,
        captcha_api_key: str,
        country: str = "us",
        request_delay: tuple[float, float] = (5.0, 15.0),
        max_retries: int = 3,
        headless: bool = True,
    ):
        self.thordata_username = thordata_username
        self.thordata_password = thordata_password
        self.captcha_api_key = captcha_api_key
        self.country = country
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.headless = headless


class ECrawler:
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.results: list[Product] = []
        self._runtime = SmartCrawlerRuntime(
            RuntimeOptions(
                proxy_username=config.thordata_username,
                proxy_password=config.thordata_password,
                captcha_api_key=config.captcha_api_key,
                output_dir="output",
                traces_dir="traces",
                concurrency=1,
            )
        )

    def crawl_search_results(self, site: str, query: str, pages: int = 3) -> list[Product]:
        batch = self._runtime.crawl(sites=[site], query=query, pages=pages)
        site_products = [product for product in batch.products if product.source == site]
        self.results.extend(site_products)
        return site_products

    def crawl_product_detail(self, site: str, url: str) -> Product:
        task = RuntimeTask(id=f"{site}-detail", site=site, url=url, goal="detail")
        batch = self._runtime.crawl_tasks([task])
        if not batch.products:
            raise ValueError(f"No product extracted for detail URL: {url}")
        product = batch.products[0]
        self.results.append(product)
        return product

    def save_results(self, output_dir: str = "output") -> None:
        grouped: dict[str, list[Product]] = {}
        for product in self.results:
            grouped.setdefault(product.source or "unknown", []).append(product)
        output_files = ProductOutputWriter(output_dir).write_products(grouped)
        log.info("results_saved", output_files=output_files, total=len(self.results))
