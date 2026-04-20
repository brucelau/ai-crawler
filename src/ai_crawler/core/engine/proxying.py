from __future__ import annotations

import time
from threading import Lock

import structlog

from ai_crawler.core.strategy import CrawlStrategy, ProxyType


log = structlog.get_logger()


class ProxyProvider:
    PLACEHOLDER_VALUES = (
        "",
        "your_thordata_username",
        "your_thordata_password",
        "none",
        "null",
    )
    _verified_proxies: dict[str, tuple[bool, float]] = {}
    _verify_lock = Lock()
    _verify_timeout = 5

    def __init__(
        self,
        username: str,
        password: str,
        default_country: str = "us",
        verify_proxy: bool = True,
        disabled: bool = False,
    ):
        self.username = username
        self.password = password
        self.default_country = default_country
        self.verify_proxy = verify_proxy
        self.disabled = disabled
        self._enabled = bool(
            not disabled
            and username
            and password
            and username not in self.PLACEHOLDER_VALUES
            and password not in self.PLACEHOLDER_VALUES
        )
        self._manager_cache: dict[ProxyType, object] = {}

    def _verify_proxy_connection(self, proxy_url: str) -> bool:
        try:
            import requests

            resp = requests.get(
                "https://httpbin.org/ip",
                proxies={"http": proxy_url, "https": proxy_url},
                timeout=self._verify_timeout,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def _is_proxy_verified(self, proxy_url: str) -> bool:
        with self._verify_lock:
            if proxy_url not in self._verified_proxies:
                return False
            is_valid, timestamp = self._verified_proxies[proxy_url]
            if not is_valid:
                return False
            if time.time() - timestamp > 60:
                del self._verified_proxies[proxy_url]
                return False
            return True

    def _mark_proxy_verified(self, proxy_url: str, success: bool) -> None:
        with self._verify_lock:
            self._verified_proxies[proxy_url] = (success, time.time())

    def _get_thordata_manager(self, pt: ProxyType):
        cached = self._manager_cache.get(pt)
        if cached is not None:
            return cached

        from ai_crawler.integrations.proxy.thordata import ThorDataManager

        country = "us"
        city = None
        proxy_host = "pr.thordata.net"

        if pt == ProxyType.THORDATA_US_CITY:
            city = "new_york"
        elif pt == ProxyType.THORDATA_DEDICATED:
            from ai_crawler.config import config

            proxy_host = config.THORDATA_PROXY_HOST

        manager = ThorDataManager(
            username=self.username,
            password=self.password,
            country=country,
            city=city,
            proxy_host=proxy_host,
            pool_size=3,
            sticky=True,
            session_duration=180,
        )
        self._manager_cache[pt] = manager
        return manager

    def proxy_url(self, strategy: CrawlStrategy) -> str | None:
        if not self._enabled:
            return None
        manager = self._get_thordata_manager(strategy.proxy)
        proxy = manager.get_proxy_url()
        if not self.verify_proxy:
            return proxy
        if proxy and self._is_proxy_verified(proxy):
            return proxy
        if proxy and self._verify_proxy_connection(proxy):
            self._mark_proxy_verified(proxy, True)
            log.info("proxy_verified", proxy_host=proxy.split("@")[-1] if "@" in proxy else proxy)
            return proxy
        if proxy:
            self._mark_proxy_verified(proxy, False)
        return None

    def rotate_proxy(self, strategy: CrawlStrategy) -> str | None:
        if not self._enabled:
            return None
        manager = self._get_thordata_manager(strategy.proxy)
        manager.rotate()
        return manager.get_proxy_url()
