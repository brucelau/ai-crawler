from typing import Optional

from scrapy import Spider, Request
from scrapy.http import Response

from ai_crawler.config import config


class ProxyMiddleware:
    def __init__(
        self,
        username: str = None,
        password: str = None,
        country: str = "us",
        disabled: bool = False,
    ):
        self.username = username or config.THORDATA_RESIDENTIAL_USERNAME
        self.password = password or config.THORDATA_RESIDENTIAL_PASSWORD
        self.country = country
        self.disabled = disabled or not (self.username and self.password)

        if not self.disabled:
            from ai_crawler.integrations.proxy.thordata import ThorDataManager

            self._manager = ThorDataManager(
                username=self.username,
                password=self.password,
                country=self.country,
                pool_size=5,
                sticky=True,
                session_duration=180,
            )
        else:
            self._manager = None

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        proxy_disabled = settings.getbool("PROXY_DISABLED", False)
        return cls(
            username=config.THORDATA_RESIDENTIAL_USERNAME,
            password=config.THORDATA_RESIDENTIAL_PASSWORD,
            country=config.THORDATA_COUNTRY,
            disabled=proxy_disabled,
        )

    def process_request(self, request: Request):
        if self.disabled:
            return None

        if request.meta.get("proxy"):
            return None

        strategy = request.meta.get("current_strategy")
        if strategy:
            proxy_type = strategy.proxy
            proxy_url = self._get_proxy_for_type(proxy_type)
            if proxy_url:
                request.meta["proxy"] = proxy_url

        return None

    def _get_proxy_for_type(self, proxy_type) -> Optional[str]:
        if not self._manager:
            return None

        return self._manager.get_proxy_url()

    def process_response(self, request: Request, response: Response):
        if response.status in (403, 429):
            if self._manager:
                spider = request.meta.get("spider")
                if spider and hasattr(spider, "logger"):
                    spider.logger.info(f"Proxy rotated due to {response.status}")

        return response

    def process_exception(self, request: Request, exception):
        if self._manager:
            spider = request.meta.get("spider")
            if spider and hasattr(spider, "logger"):
                spider.logger.info("Proxy rotated due to exception")

        return None


class HumanBehaviorMiddleware:
    def __init__(self):
        self.scroll_enabled = True
        self.mouse_enabled = True

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def process_request(self, request: Request):
        return None

    def process_response(self, request: Request, response: Response):
        strategy = request.meta.get("current_strategy")
        if strategy and strategy.use_human_scroll:
            request.meta["human_scroll"] = True
        return response
