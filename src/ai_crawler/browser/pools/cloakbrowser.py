import structlog
from ai_crawler.core.types import CrawlPolicy, CrawlTask
from ai_crawler.browser import utils
from ai_crawler.browser.pools.state import PoolState


log = structlog.get_logger()


class CloakBrowserPool:
    def __init__(
        self,
        state: PoolState,
        proxy_provider=None,
        dynamic_profile: dict | None = None,
        page_load_timeout: float = 30.0,
    ):
        self._state = state
        self.proxy_provider = proxy_provider
        self.dynamic_profile = dynamic_profile or {}
        self.page_load_timeout = page_load_timeout

    def fetch(self, task: CrawlTask, strategy: CrawlPolicy) -> tuple[str, int | None, any]:
        import time
        import random

        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))
        try:
            proxy = self.proxy_provider.proxy_url(strategy) if self.proxy_provider else None
            proxy_settings = utils.structured_proxy_settings(proxy)
            launch_kwargs = {"headless": True}
            if proxy_settings:
                launch_kwargs["proxy"] = proxy_settings.get("server")
            browser_key = utils.stable_key(launch_kwargs)
            browser = self._get_cloak_browser(browser_key, launch_kwargs)

            page = browser.new_page()
            self._state.increment_stat("pages_opened")
            page.set_default_timeout(self.page_load_timeout * 1000)
            resp = page.goto(
                task.url,
                wait_until="domcontentloaded",
                timeout=int(self.page_load_timeout * 1000),
            )
            content = page.content()
            status = resp.status if resp else 200
            return content, status, page
        except Exception as exc:
            log.warning("cloakbrowser_error", url=task.url, error=str(exc))
            return "", None, None

    def _get_cloak_browser(self, browser_key: str, launch_kwargs: dict):
        with self._state._pool_lock:
            browser = self._state._cloak_browsers.get(browser_key)
            if browser is not None:
                self._state.increment_stat("cloak_browser_reused")
                log.info("cloak_browser_reused", browser_key=browser_key)
                return browser

            from cloakbrowser import launch

            browser = launch(**launch_kwargs)
            self._state._cloak_browsers[browser_key] = browser
            self._state.increment_stat("cloak_browser_created")
            log.info("cloak_browser_created", browser_key=browser_key)
            return browser
