from ai_crawler.config import setup_logging
from ai_crawler.core.runner import CrawlRunner
from ai_crawler.core.engine.results import CrawlResult
from ai_crawler.core.engine.trace_store import TraceStore
from ai_crawler.core.types import CrawlStrategy, CrawlTask, ProxyType, RenderType
from ai_crawler.api import RuntimeBatchResult, RuntimeOptions, RuntimeTask, SmartCrawlerRuntime
from ai_crawler.api.orchestrator import SUPPORTED_SITES
from ai_crawler.models.product import Product

try:
    from ai_crawler.spiders import EXTRACTORS
except ModuleNotFoundError:
    EXTRACTORS = {}


ProductsResult = RuntimeBatchResult


def run_crawl(
    sites: list[str],
    query: str,
    pages: int,
    proxy_username: str = "",
    proxy_password: str = "",
    llm_api_key: str | None = None,
    captcha_api_key: str | None = None,
    output_dir: str = "output",
    traces_dir: str = "traces",
    max_ip_retries: int = 3,
    proxy_disabled: bool = False,
) -> ProductsResult:
    runtime = SmartCrawlerRuntime(
        RuntimeOptions(
            proxy_username=proxy_username,
            proxy_password=proxy_password,
            llm_api_key=llm_api_key,
            captcha_api_key=captcha_api_key,
            output_dir=output_dir,
            traces_dir=traces_dir,
            max_ip_retries=max_ip_retries,
            proxy_disabled=proxy_disabled,
            concurrency=1,
        )
    )
    return runtime.crawl(sites=sites, query=query, pages=pages)


def _build_url(site: str, query: str, page: int) -> str:
    return SmartCrawlerRuntime.build_search_url(site, query, page)


__all__ = [
    "CrawlRunner",
    "CrawlTask",
    "CrawlStrategy",
    "ProxyType",
    "RenderType",
    "TraceStore",
    "CrawlResult",
    "ProductsResult",
    "RuntimeTask",
    "RuntimeOptions",
    "SmartCrawlerRuntime",
    "EXTRACTORS",
    "Product",
    "run_crawl",
    "setup_logging",
    "SUPPORTED_SITES",
]
