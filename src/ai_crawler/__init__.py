from ai_crawler.core.config import setup_logging
from ai_crawler.core.sites import SUPPORTED_SITES
from ai_crawler.core.types import CrawlPolicy, CrawlTask, Product, ProxyType, RenderType
from ai_crawler.crawl.orchestrator import RuntimeOptions, SmartCrawlerRuntime
from ai_crawler.crawl.runner import CrawlRunner
from ai_crawler.crawl.results import CrawlResult
from ai_crawler.storage.trace_store import TraceStore
from ai_crawler.core.types import RuntimeBatchResult, RuntimeTask

ProductsResult = RuntimeBatchResult
EXTRACTORS = SUPPORTED_SITES  # backward compat
CrawlStrategy = CrawlPolicy   # backward compat


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
    storage_backend=None,
    save_html: bool = False,
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
            save_html=save_html,
        )
    )
    return runtime.crawl(sites=sites, query=query, pages=pages, storage_backend=storage_backend)


def _build_url(site: str, query: str, page: int) -> str:
    return SmartCrawlerRuntime.build_search_url(site, query, page)


__all__ = [
    "CrawlRunner",
    "CrawlTask",
    "CrawlPolicy",
    "ProxyType",
    "RenderType",
    "TraceStore",
    "CrawlResult",
    "ProductsResult",
    "RuntimeTask",
    "RuntimeOptions",
    "SmartCrawlerRuntime",
    "Product",
    "run_crawl",
    "setup_logging",
    "SUPPORTED_SITES",
]
