from __future__ import annotations

from scrapy.settings import Settings

from ai_crawler.config import config
from ai_crawler.api import RuntimeOptions, SmartCrawlerRuntime


class ScrapyRuntimeBridge:
    def __init__(self, settings: Settings):
        self.settings = settings

    def run(self, sites: list[str], query: str, pages: int):
        runtime = SmartCrawlerRuntime(self._build_options())
        return runtime.crawl(sites=sites, query=query, pages=pages)

    def _build_options(self) -> RuntimeOptions:
        return RuntimeOptions(
            proxy_username=config.THORDATA_RESIDENTIAL_USERNAME,
            proxy_password=config.THORDATA_RESIDENTIAL_PASSWORD,
            llm_api_key=self.settings.get("LLM_API_KEY") or config.OPENAI_API_KEY,
            captcha_api_key=self.settings.get("CAPTCHA_API_KEY") or config.TWO_CAPTCHA_API_KEY,
            output_dir=self.settings.get("OUTPUT_DIR", "output"),
            traces_dir=self.settings.get("TRACE_DIR", "traces"),
            max_ip_retries=self.settings.getint("MAX_IP_RETRIES", 3),
            proxy_disabled=self.settings.getbool("PROXY_DISABLED", config.PROXY_DISABLED),
            concurrency=self.settings.getint("RUNTIME_CONCURRENCY", 1),
        )
