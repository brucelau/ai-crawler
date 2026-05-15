import time
import random
import structlog
from collections import OrderedDict
from ai_crawler.spider.runtime.crawl import CrawlPolicy, CrawlTask
from ai_crawler.browser import utils
from ai_crawler.browser.pools.state import PoolState


log = structlog.get_logger()


class UCPool:
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
        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))
        driver = None
        driver_key = ""
        try:
            proxy = self.proxy_provider.proxy_url(strategy) if self.proxy_provider else None
            proxy_settings = utils.structured_proxy_settings(proxy)
            if proxy_settings and (
                proxy_settings.get("username") or proxy_settings.get("password")
            ):
                bridge = self._get_uc_proxy_bridge(proxy)
                local_proxy_url = bridge.local_proxy_url()
                proxy_settings = utils.structured_proxy_settings(local_proxy_url)
            driver_key = utils.stable_key(
                {
                    "proxy": proxy_settings.get("server") if proxy_settings else None,
                    "site": task.site,
                    "headless": True,
                    "change_ua": strategy.change_ua,
                    "user_agent": self.dynamic_profile.get("user_agent")
                    if strategy.change_ua
                    else None,
                }
            )
            driver = self._get_uc_driver(
                driver_key,
                strategy,
                proxy_settings.get("server") if proxy_settings else None,
            )
            driver.get(task.url)
            time.sleep(5)
            content = driver.page_source
            salvaged_html = ""
            if self._can_salvage_uc_html(content):
                salvaged_html = content
            else:
                try:
                    salvaged_html = driver.page_source or ""
                except Exception:
                    salvaged_html = ""

            if self._can_salvage_uc_html(salvaged_html):
                if driver is not None and driver_key:
                    self._release_uc_driver(
                        driver_key,
                        driver,
                        healthy=self._reset_uc_driver(driver),
                    )
                return salvaged_html, 200, None

            if driver is not None and driver_key:
                self._release_uc_driver(driver_key, driver, healthy=False)
            log.warning("uc_error", url=task.url)
            return "", None, None
        except Exception as exc:
            if driver is not None and driver_key:
                self._release_uc_driver(driver_key, driver, healthy=False)
            log.warning("uc_error", url=task.url, error=str(exc))
            return "", None, None

    def _get_uc_proxy_bridge(self, upstream_proxy_url: str):
        from ai_crawler.spider.engine.proxy.uc_bridge import UCProxyBridge

        with self._state._pool_lock:
            bridge = self._state._uc_proxy_bridges.get(upstream_proxy_url)
            if bridge is not None and bridge.healthy():
                return bridge
            if bridge is not None:
                try:
                    bridge.stop()
                except Exception:
                    pass
            bridge = UCProxyBridge(upstream_proxy_url)
            bridge.start()
            self._state._uc_proxy_bridges[upstream_proxy_url] = bridge
            return bridge

    def _is_uc_driver_healthy(self, driver) -> bool:
        try:
            handles = getattr(driver, "window_handles", None)
            if not handles:
                return False
            _ = driver.current_window_handle
            if hasattr(driver, "execute_script"):
                driver.execute_script("return 1")
            return True
        except Exception:
            self._state.increment_stat("uc_healthcheck_failed")
            return False

    def _evict_uc_driver(self, driver_key: str) -> None:
        driver = self._state._uc_drivers.pop(driver_key, None)
        self._state._uc_driver_meta.pop(driver_key, None)
        if driver is None:
            return
        try:
            driver.quit()
        except Exception:
            pass
        self._state.increment_stat("uc_browser_evicted")
        log.info("uc_browser_evicted", driver_key=driver_key)

    def _trim_uc_pool(self) -> None:
        while len(self._state._uc_drivers) >= self._state._uc_pool_cap:
            oldest_key = next(iter(self._state._uc_drivers))
            self._evict_uc_driver(oldest_key)

    def _reset_uc_driver(self, driver) -> bool:
        try:
            if hasattr(driver, "delete_all_cookies"):
                driver.delete_all_cookies()
            driver.get("about:blank")
            if hasattr(driver, "execute_script"):
                driver.execute_script(
                    "try { localStorage.clear(); sessionStorage.clear(); } catch (e) {}"
                )
            return self._is_uc_driver_healthy(driver)
        except Exception:
            self._state.increment_stat("uc_reset_failed")
            return False

    def _build_uc_options(self, strategy: CrawlPolicy, proxy: str | None):
        import undetected_chromedriver as uc

        options = uc.ChromeOptions()
        options.headless = True
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.page_load_strategy = "eager"
        if proxy:
            options.add_argument(f"--proxy-server={proxy}")
        user_agent = self.dynamic_profile.get("user_agent")
        if strategy.change_ua and user_agent:
            options.add_argument(f"--user-agent={user_agent}")
        return options

    def _get_uc_driver(self, driver_key: str, strategy: CrawlPolicy, proxy: str | None):
        import undetected_chromedriver as uc

        with self._state._pool_lock:
            driver = self._state._uc_drivers.get(driver_key)
            if driver is not None:
                meta = self._state._uc_driver_meta.get(driver_key, {})
                idle = time.time() - float(meta.get("last_used", time.time()))
                leases = int(meta.get("leases", 0))
                if idle > self._state._uc_idle_ttl_seconds or leases >= self._state._uc_max_leases:
                    self._evict_uc_driver(driver_key)
                    driver = None
                elif self._is_uc_driver_healthy(driver):
                    self._state._uc_drivers.move_to_end(driver_key)
                    self._state.increment_stat("uc_browser_reused")
                    log.info("uc_browser_reused", driver_key=driver_key)
                    return driver
                else:
                    self._evict_uc_driver(driver_key)
                    driver = None

            self._trim_uc_pool()
            options = self._build_uc_options(strategy, proxy)
            driver = uc.Chrome(options=options, version_main=None)
            driver.set_page_load_timeout(20)
            try:
                driver.set_script_timeout(20)
            except Exception:
                pass
            self._state._uc_drivers[driver_key] = driver
            self._state._uc_driver_meta[driver_key] = {"leases": 0, "last_used": time.time()}
            self._state.increment_stat("uc_browser_created")
            log.info("uc_browser_created", driver_key=driver_key)
            return driver

    def _release_uc_driver(self, driver_key: str, driver, healthy: bool) -> None:
        with self._state._pool_lock:
            if not healthy:
                self._evict_uc_driver(driver_key)
                return
            meta = self._state._uc_driver_meta.setdefault(
                driver_key, {"leases": 0, "last_used": time.time()}
            )
            meta["leases"] = int(meta.get("leases", 0)) + 1
            meta["last_used"] = time.time()
            self._state._uc_drivers[driver_key] = driver
            self._state._uc_drivers.move_to_end(driver_key)

    @staticmethod
    def _can_salvage_uc_html(html: str) -> bool:
        lowered = (html or "").lower()
        if len(html or "") < 50000:
            return False
        hard_error_markers = [
            "err_no_supported_proxies",
            "this site can't be reached",
            "chrome-error://",
            "sorry! something went wrong!",
            "we couldn't process your request",
        ]
        return not any(marker in lowered for marker in hard_error_markers)
